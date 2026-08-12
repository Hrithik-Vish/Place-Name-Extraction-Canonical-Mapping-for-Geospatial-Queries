-- ============================================================
-- PS-09: Place-Name Extraction & Canonical Mapping
-- PostgreSQL + PostGIS Schema
-- ============================================================

-- Enable PostGIS extension (must run first, before any spatial columns)
CREATE EXTENSION IF NOT EXISTS postgis;


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
-- This is what the fuzzy-matching cleanup step queries against.
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

-- Requires pg_trgm for fuzzy/similarity search support (used alongside rapidfuzz)
CREATE EXTENSION IF NOT EXISTS pg_trgm;


-- ============================================================
-- 3. RESULT DATA: resolved_places
-- Written to by the backend after every /resolve request.
-- Acts as both a cache and a demo-able log of system decisions.
-- ============================================================
CREATE TABLE resolved_places (
    id                  BIGSERIAL PRIMARY KEY,
    request_id           UUID DEFAULT gen_random_uuid(),  -- groups all places from one submitted text
    original_text         TEXT NOT NULL,           -- full submitted sentence
    raw_name               TEXT NOT NULL,           -- extracted string, as found in text (e.g. "Springfield")
    cleaned_name            TEXT,                    -- after fuzzy/alias cleanup
    canonical_name           TEXT NOT NULL,           -- resolved official name
    canonical_geoname_id      BIGINT REFERENCES geonames_places(geoname_id),
    latitude                  DOUBLE PRECISION NOT NULL,
    longitude                  DOUBLE PRECISION NOT NULL,
    geom                        GEOGRAPHY(POINT, 4326),
    confidence                  NUMERIC(4,3) NOT NULL,   -- 0.000 - 1.000
    reason                       TEXT,                    -- human-readable disambiguation explanation
    source                        TEXT,                    -- 'local_geonames' or 'nominatim_fallback'
    candidate_count                INTEGER DEFAULT 1,      -- how many candidates were considered
    created_at                      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_resolved_places_raw_name ON resolved_places (raw_name);
CREATE INDEX idx_resolved_places_original_text ON resolved_places USING gin (to_tsvector('english', original_text));
CREATE INDEX idx_resolved_places_geom ON resolved_places USING gist (geom);
CREATE INDEX idx_resolved_places_request_id ON resolved_places (request_id);
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
-- 4. CACHE LOOKUP HELPER VIEW (optional convenience)
-- Quick way to check "have we already resolved this exact raw_name
-- from this exact original_text before?" for the caching step.
-- ============================================================
CREATE OR REPLACE VIEW resolved_places_cache_lookup AS
SELECT DISTINCT ON (original_text, raw_name)
    original_text,
    raw_name,
    canonical_name,
    latitude,
    longitude,
    confidence,
    reason,
    created_at
FROM resolved_places
ORDER BY original_text, raw_name, created_at DESC;


-- ============================================================
-- 5. EXAMPLE SPATIAL QUERY (for the stretch-goal "query mode")
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
