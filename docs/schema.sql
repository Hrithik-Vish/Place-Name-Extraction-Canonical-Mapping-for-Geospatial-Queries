-- ============================================================
-- PS-09: Place-Name Extraction & Canonical Mapping
-- PostgreSQL + PostGIS Schema
-- v2 — introduces raw_name_aliases for fast-path caching
-- (full rebuild — run against a clean database)
-- ============================================================

-- Enable required extensions (must run first, before any spatial/trgm columns)
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- needed for gen_random_uuid()


-- ============================================================
-- 1. REFERENCE DATA: geonames_places
-- Bulk-loaded once from GeoNames India (IN.zip) flat file.
-- This is the canonical source of truth for real-world places.
-- ============================================================
CREATE TABLE geonames_places (
    geoname_id      BIGINT PRIMARY KEY,          -- GeoNames' own unique ID
    name            TEXT NOT NULL,               -- official/canonical name
    ascii_name      TEXT,                        -- ASCII-normalized name (for matching)
    latitude        DOUBLE PRECISION NOT NULL,
    longitude       DOUBLE PRECISION NOT NULL,
    geom            GEOGRAPHY(POINT, 4326),       -- PostGIS spatial point, derived from lat/long
    feature_class   CHAR(1),                     -- GeoNames feature class (e.g. 'P' = populated place)
    feature_code    VARCHAR(10),                 -- GeoNames feature code (e.g. 'PPL', 'PPLA')
    country_code    VARCHAR(2),                  -- ISO country code (e.g. 'IN')
    admin1_code     VARCHAR(20),                 -- state/region code
    admin2_code     VARCHAR(80),                 -- district code
    population      BIGINT DEFAULT 0,            -- used as a disambiguation ranking signal
    elevation       INTEGER,
    timezone        TEXT,
    modification_date DATE
);

-- Indexes for fast name lookup and spatial queries
CREATE INDEX idx_geonames_places_name ON geonames_places (name);
CREATE INDEX idx_geonames_places_ascii_name ON geonames_places (ascii_name);
CREATE INDEX idx_geonames_places_name_trgm ON geonames_places USING gin (name gin_trgm_ops);
CREATE INDEX idx_geonames_places_geom ON geonames_places USING gist (geom);
CREATE INDEX idx_geonames_places_country ON geonames_places (country_code);

-- Trigger to auto-populate geom from lat/long on insert/update
CREATE OR REPLACE FUNCTION geonames_places_set_geom()
RETURNS TRIGGER AS $$
BEGIN
    NEW.geom := ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326)::geography;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_geonames_places_set_geom
BEFORE INSERT OR UPDATE ON geonames_places
FOR EACH ROW EXECUTE FUNCTION geonames_places_set_geom();


-- ============================================================
-- 2. REFERENCE DATA: geonames_alternate_names
-- Bulk-loaded once from GeoNames alternateNames file.
-- Maps aliases / historical names / colloquial names -> canonical place.
-- This is what the fuzzy-matching cleanup step (Task 6) queries against.
-- ============================================================
CREATE TABLE geonames_alternate_names (
    alternate_name_id  BIGINT PRIMARY KEY,       -- GeoNames' own unique ID
    geoname_id          BIGINT NOT NULL REFERENCES geonames_places(geoname_id) ON DELETE CASCADE,
    iso_language        VARCHAR(7),              -- language code, or 'link', 'abbr', etc.
    alternate_name       TEXT NOT NULL,           -- e.g. "Bombay"
    is_preferred_name    BOOLEAN DEFAULT FALSE,
    is_short_name         BOOLEAN DEFAULT FALSE,
    is_colloquial          BOOLEAN DEFAULT FALSE,
    is_historic             BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_alt_names_alternate_name ON geonames_alternate_names (alternate_name);
CREATE INDEX idx_alt_names_alternate_name_trgm ON geonames_alternate_names USING gin (alternate_name gin_trgm_ops);
CREATE INDEX idx_alt_names_geoname_id ON geonames_alternate_names (geoname_id);


-- ============================================================
-- 3. RESULT DATA: resolved_places
-- One row per DISTINCT resolved cleaned_name (not per raw span,
-- not per sentence). This is the canonical resolution + disambiguation
-- record — written once per unique cleaned_name, then reused by every
-- raw_name_aliases row that points to it.
--
-- MVP SCOPE: this table only ever holds successful resolutions.
-- A name that fails to resolve (no GeoNames match, no Nominatim match)
-- is NOT written here and NOT cached anywhere — it always retries the
-- full pipeline fresh on every occurrence. Caching failures would need
-- a TTL/invalidation strategy (a Nominatim timeout today isn't
-- necessarily a timeout tomorrow) that isn't worth building for a
-- demo-scope MVP. Noted as a future-scope item, not built here.
-- ============================================================
CREATE TABLE resolved_places (
    id                  BIGSERIAL PRIMARY KEY,
    cleaned_name          TEXT NOT NULL,           -- post-cleanup/alias-normalized name; the lookup key
    canonical_name          TEXT NOT NULL,           -- resolved official name
    canonical_geoname_id      BIGINT REFERENCES geonames_places(geoname_id),  -- null if resolved via Nominatim
    latitude                   DOUBLE PRECISION NOT NULL,
    longitude                   DOUBLE PRECISION NOT NULL,
    geom                         GEOGRAPHY(POINT, 4326),
    confidence                    NUMERIC(4,3) NOT NULL,  -- 0.000 - 1.000
    reason                         TEXT,                    -- human-readable disambiguation explanation
    source                          TEXT NOT NULL,           -- 'local_geonames' or 'nominatim_fallback'
    candidate_count                  INTEGER DEFAULT 1,      -- how many candidates were considered
    created_at                        TIMESTAMPTZ DEFAULT now(),
    updated_at                         TIMESTAMPTZ DEFAULT now()
);

-- One resolution per distinct cleaned_name — this is what makes the
-- alias table's fast path meaningful (nothing to point to twice).
CREATE UNIQUE INDEX idx_resolved_places_cleaned_name_unique ON resolved_places (cleaned_name);
CREATE INDEX idx_resolved_places_geom ON resolved_places USING gist (geom);
CREATE INDEX idx_resolved_places_created_at ON resolved_places (created_at);

-- Trigger to auto-populate geom from lat/long, same as geonames_places
CREATE OR REPLACE FUNCTION resolved_places_set_geom()
RETURNS TRIGGER AS $$
BEGIN
    NEW.geom := ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326)::geography;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_resolved_places_set_geom
BEFORE INSERT OR UPDATE ON resolved_places
FOR EACH ROW EXECUTE FUNCTION resolved_places_set_geom();


-- ============================================================
-- 4. FAST-PATH LOOKUP: raw_name_aliases
-- Maps every raw span ever extracted by spaCy back to the
-- resolved_places row it ultimately resolved to. This is the
-- FIRST thing Task 10's cache check queries — a hit here skips
-- cleanup, GeoNames/Nominatim lookup, AND disambiguation entirely.
--
-- A miss here does NOT mean "never seen" — it falls through to
-- cleanup (Task 6), which may still land on an existing
-- resolved_places.cleaned_name. In that case, write a NEW row here
-- linking this raw_name to the EXISTING resolved_places row (no new
-- resolution needed, just a new alias mapping) so the next time this
-- exact raw_name appears, it hits the fast path too.
-- ============================================================
CREATE TABLE raw_name_aliases (
    id                  BIGSERIAL PRIMARY KEY,
    raw_name             TEXT NOT NULL,           -- exact string as spaCy extracted it (e.g. "Springfield", "bombay ")
    resolved_place_id     BIGINT NOT NULL REFERENCES resolved_places(id) ON DELETE CASCADE,
    first_seen_at           TIMESTAMPTZ DEFAULT now(),
    last_seen_at             TIMESTAMPTZ DEFAULT now(),
    hit_count                 INTEGER DEFAULT 1       -- optional: how many times this exact raw_name has been looked up
);

-- One alias mapping per distinct raw_name — prevents duplicate rows
-- for the same raw string across repeated fresh-resolution attempts.
CREATE UNIQUE INDEX idx_raw_name_aliases_raw_name_unique ON raw_name_aliases (raw_name);
CREATE INDEX idx_raw_name_aliases_resolved_place_id ON raw_name_aliases (resolved_place_id);


-- ============================================================
-- 5. REQUEST LOG: resolution_requests (optional but recommended)
-- One row per /resolve call, for the original_text + full extracted[]
-- ordering — since original_text and per-request ordering no longer
-- live on resolved_places itself (that table is now keyed by
-- cleaned_name, shared across many requests/sentences).
-- Useful for demo history, debugging, and the "submit same sentence
-- twice" test case in Task 14 — not required for the core pipeline
-- to function, but keeps a demo-able log of what was submitted when.
-- ============================================================
CREATE TABLE resolution_requests (
    id                  BIGSERIAL PRIMARY KEY,
    request_id            UUID DEFAULT gen_random_uuid(),
    original_text           TEXT NOT NULL,
    created_at                TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_resolution_requests_original_text ON resolution_requests USING gin (to_tsvector('english', original_text));
CREATE INDEX idx_resolution_requests_created_at ON resolution_requests (created_at);

-- Links each request to the raw_name_aliases rows it touched, in
-- original order — this is what Task 12 (response assembly) reads
-- to rebuild extracted[] in the order names appeared in the text.
CREATE TABLE resolution_request_items (
    id                  BIGSERIAL PRIMARY KEY,
    request_id            BIGINT NOT NULL REFERENCES resolution_requests(id) ON DELETE CASCADE,
    raw_name_alias_id      BIGINT NOT NULL REFERENCES raw_name_aliases(id),
    position_in_text         INTEGER NOT NULL   -- 0-indexed order of appearance in original_text
);

CREATE INDEX idx_resolution_request_items_request_id ON resolution_request_items (request_id, position_in_text);


-- ============================================================
-- 6. FAST-PATH LOOKUP HELPER VIEW
-- Task 10's cache check queries this first: "have we ever seen this
-- exact raw_name before, and what did it resolve to?"
-- A hit means: skip cleanup, skip GeoNames/Nominatim, skip
-- disambiguation — go straight to response assembly with these values.
-- (A miss says nothing about failure — it only ever means "not cached
-- yet"; failed resolutions are never written here, see Section 3.)
-- ============================================================
CREATE OR REPLACE VIEW raw_name_fast_path AS
SELECT
    a.raw_name,
    a.hit_count,
    r.id AS resolved_place_id,
    r.cleaned_name,
    r.canonical_name,
    r.latitude,
    r.longitude,
    r.confidence,
    r.reason,
    r.source
FROM raw_name_aliases a
JOIN resolved_places r ON r.id = a.resolved_place_id;


-- ============================================================
-- 7. EXAMPLE SPATIAL QUERY (for the stretch-goal "query mode")
-- Find all resolved places within N meters of a given point.
-- Left here as reference, not executed at schema-creation time.
-- ============================================================
-- SELECT canonical_name, latitude, longitude
-- FROM resolved_places
-- WHERE ST_DWithin(
--     geom,
--     ST_SetSRID(ST_MakePoint(72.9781, 19.2183), 4326)::geography,  -- e.g. Thane
--     20000  -- 20km in meters
-- );
