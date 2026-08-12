# Backend Build Guide — PS-09 Place-Name Extraction & Canonical Mapping

## 1. Purpose & How to Read This Doc

This document covers the full backend pipeline behind `POST /resolve`. It's split across two owners working on one coupled chain — tasks aren't independent modules, each stage feeds the next, so a stage can't be fully tested in total isolation from its neighbors (see Section 4 for how to fake your way around that during parallel dev).

**Owners:**
- **User (you):** Task 1 (Supabase + PostGIS setup), Task 2 (run schema.sql), Task 9 (disambiguation logic), Task 12 (response assembly), Task 14 (testing)
- **Member 3:** Task 4 (FastAPI endpoint), Task 5 (spaCy extraction), Task 6 (rapidfuzz cleanup), Task 7 (GeoNames candidate lookup), Task 10 (cache check + storage write)

**Reference docs:**
- `contract.md` — exact request/response JSON shape. This is the final source of truth for what the endpoint sends back. If anything in this doc seems to disagree with contract.md, contract.md wins.
- `schema.sql` — table structure. Already created and run (Task 2).

Tasks below are ordered by **pipeline position**, not by owner, so you can see where your piece sits relative to Member 3's.

---

## 2. Pipeline Overview

```
POST /resolve receives { text }
        ↓
spaCy extraction — pull every place-name span out of the text
        ↓
For EACH extracted name, individually:
        ↓
   Check resolved_places cache for (original_text, raw_name)
        ↓
   ┌─────────────────┴─────────────────┐
   CACHE HIT                        CACHE MISS
   ↓                                     ↓
   Use stored canonical/lat/long/    rapidfuzz cleanup (normalize spelling,
   confidence/reason/source          strip noise, match known aliases)
   directly                                ↓
   ↓                                 Local GeoNames lookup
   ↓                                       ↓
   ↓                                 Found locally? ──No──→ Nominatim fallback
   ↓                                       ↓ Yes                   ↓
   ↓                                       ↓                  Found? ──No──→
   ↓                                       ↓                       ↓         mark status: "failed"
   ↓                                       └───────┬───────────────┘
   ↓                                               ↓
   ↓                                        Disambiguation (population,
   ↓                                        proximity, region hints →
   ↓                                        confidence + reason)
   ↓                                               ↓
   ↓                                        Write fresh result to
   ↓                                        resolved_places cache
   └─────────────────┬─────────────────────────────┘
                      ↓
        Response assembly — combine all resolved
        (cached + freshly resolved) + failed entries
        into one extracted[] array, in original order
                      ↓
              Return JSON per contract.md
```

**Key point:** caching is per-name, not per-sentence. If a sentence has 3 names and 1 is already cached, only the other 2 run through the full pipeline. Nothing reruns from scratch just because one name is new.

**Short-circuit case:** if spaCy finds zero names at all, skip everything after extraction and return immediately per contract.md Section 5.2 (empty `extracted` array + message).

---

## 3. Per-Task Breakdown

### Task 1 — Supabase Project Setup (User)
**What:** Create the Supabase project. Enable the `postgis` and `pg_trgm` extensions. Confirm `pgcrypto` is enabled (needed for `gen_random_uuid()` in schema.sql — usually on by default in Supabase, but verify).
**Input:** None — this is the foundation everything else sits on.
**Output:** A live Supabase project with the right extensions on, and a connection string/API key ready to share with Member 3 and Member 4 (needed for Task 3 — CSV loading).
**Done when:** You can run a test query like `SELECT postgis_version();` and `SELECT * FROM pg_extension;` and see `postgis`, `pg_trgm`, and `pgcrypto` all listed.

### Task 2 — Run schema.sql (User)
**What:** Execute `schema.sql` against the Supabase project to create `geonames_places`, `geonames_alternate_names`, `resolved_places`, and the `resolved_places_cache_lookup` view.
**Input:** The Supabase project from Task 1, `schema.sql`.
**Output:** All tables and the cache-lookup view exist and are queryable.
**Done when:** All 3 tables + 1 view show up in the Supabase table editor, and the auto-`geom` triggers work — insert a test row with lat/long into `geonames_places` and confirm `geom` populates automatically.

### Task 4 — Bare FastAPI Endpoint (Member 3)
**What:** Stand up `POST /resolve` in FastAPI. At this stage it just needs to accept `{ "text": string }`, validate the shape (not the emptiness — frontend handles that per contract.md 5.1), and return a hardcoded placeholder response matching contract.md's shape exactly. This is the scaffold everything else plugs into.
**Input:** Raw request body.
**Output:** A response matching contract.md's structure (even with fake data at first) — this lets frontend start integrating against something real immediately.
**Done when:** Sending a POST with `{ "text": "test" }` via curl/Postman returns valid JSON matching the contract's field names and types exactly.

### Task 5 — spaCy Extraction (Member 3)
**What:** Wire in `en_core_web_sm`, run NER on `text`, pull out every entity spaCy tags as a location (GPE/LOC labels). No cleanup yet — raw spans only.
**Input:** The `text` string from the request.
**Output:** A list of raw name strings (e.g. `["Thane", "Kalyan", "Springfield"]`) in the order they appear in the text.
**Done when:** Running it against the test sentence in contract.md Section 4 produces exactly `["Thane", "Kalyan", "Springfield"]`. Also test against a sentence with zero locations to confirm it returns an empty list cleanly (this feeds the short-circuit case).

### Task 6 — rapidfuzz Cleanup (Member 3)
**What:** Take each raw name from Task 5 and normalize it — strip stray punctuation/whitespace, and fuzzy-match against known aliases (e.g. historical names like "Bombay" → "Mumbai") using the `geonames_alternate_names` table.
**Input:** One raw name string.
**Output:** A cleaned name string, ready for GeoNames lookup. If no alias match is found, pass the raw name through unchanged (don't force a bad match).
**Done when:** Feeding it "Bombay" returns "Mumbai" (or whatever your alternate-names data has), and feeding it "Thane" (no alias needed) returns "Thane" unchanged.

### Task 7 — Local GeoNames Candidate Lookup (Member 3)
**What:** Query `geonames_places` for matches against the cleaned name. Can return multiple candidates (e.g. multiple "Springfield"s in the data) — that's expected, disambiguation (Task 9) sorts them out.
**Input:** A cleaned name string.
**Output:** A list of candidate rows from `geonames_places` (each with lat/long/population/admin info), or an empty list if nothing matches locally.
**Done when:** Querying "Thane" returns at least one candidate with correct lat/long. Querying a clearly-not-in-India name confirms an empty list comes back cleanly (this is what should trigger Nominatim fallback — Member 4's Task 8).

### Task 8 — Nominatim Fallback (Member 4)
*(Owned by Member 4 — listed here because it sits directly between Task 7 and Task 9 in the pipeline. Full detail lives in `member4_tasks.md`.)*
**What:** If Task 7 returns zero local candidates, call the Nominatim API as a live backup.
**Input:** The cleaned name string.
**Output:** Either a candidate (lat/long + display name) formatted to look like a GeoNames candidate, or nothing (triggering a `"failed"` entry).
**Note for you both:** Nominatim has a 1 request/second rate limit and requires a `User-Agent` header — make sure Task 9's disambiguation logic can accept candidates from either source (`local_geonames` or `nominatim_fallback`) in the same shape.

### Task 9 — Disambiguation Logic (User)
**What:** Given one or more candidates (from Task 7 and/or Task 8) for a single name, pick the best match. Scoring factors: population size (bigger cities more likely to be the intended place), proximity to other already-resolved names in the same text (e.g. if "Thane" resolved nearby, a candidate close to it is more likely correct for the next name), and any region/state hints present in the surrounding text. Produce a `confidence` score (0.0–1.0 float) and a human-readable `reason` string explaining the choice.
**Input:** A list of candidates for one name, plus the set of already-resolved names/coordinates from earlier in the same request (for proximity scoring).
**Output:** One chosen candidate (canonical name, lat, long, source) + `confidence` + `reason`. If no candidates exist at all (Task 7 and Task 8 both came back empty), output a `"failed"` entry instead — `canonical`/`lat`/`long`/`source` all `null`, `confidence: 0.0`, `reason` explaining nothing was found.
**Done when:** Feeding it the Thane/Kalyan/Springfield example produces confidence scores and reasons that read sensibly — this is the single most demo-critical piece of logic, since the click-to-reveal "reason" field is what proves the system reasons rather than just retrieves.

### Task 10 — Cache Check + Storage Write (Member 3)
**What:** Two responsibilities folded into one task:
1. **Before** running cleanup/lookup/disambiguation for a given name, check `resolved_places_cache_lookup` for an existing entry matching `(original_text, raw_name)`. If found, skip straight to using the cached values for that name.
2. **After** a name is freshly resolved (or freshly failed) via the full pipeline, write the result into `resolved_places`.
**Input:** The raw name (for cache check) or the fully resolved/failed result (for the write).
**Output:** Either a cache hit (existing row) or a new row written to `resolved_places`.
**Done when:** Submitting the same sentence twice — the second time, cached names skip the pipeline entirely (verify via logging/timing that GeoNames/Nominatim/disambiguation don't re-run for already-cached names), while any new name in the sentence still runs fresh.

### Task 12 — Response Assembly / Final Endpoint Wiring (User)
**What:** Combine the results for every name in the request — whether they came from cache or were freshly resolved or failed — into the final `extracted[]` array, preserving the original order names appeared in the text. Wrap with `original_text` and `message` (null in the normal case) per contract.md.
**Input:** A set of per-name results (cached + freshly resolved + failed), plus the original request text.
**Output:** The final JSON response exactly matching contract.md's success-case shape.
**Done when:** The full pipeline, run end to end on the Thane/Kalyan/Springfield sentence, produces JSON that matches contract.md Section 4's example exactly in structure (values will vary slightly based on real data, but field names/types/nesting must match precisely).

### Task 14 — Testing (User)
**What:** Test the full assembled pipeline against a range of inputs: the standard example sentence, a sentence with zero locations (confirms short-circuit), a sentence where one name is real but unfindable (confirms partial-failure shape), and a repeat submission (confirms caching actually skips work). Also sanity-check response times to make sure nothing hangs (especially around Nominatim's rate limit).
**Input:** The fully wired `/resolve` endpoint.
**Output:** A short list of confirmed-working test cases, and a list of any contract mismatches found and fixed before frontend integration.
**Done when:** All 3 edge cases from contract.md Section 5 produce exactly the shapes documented there, verified against real running code, not just read through.

---

## 4. Local Dev / Testing Notes — Working in Parallel

You and Member 3 don't have to build strictly in sequence. Fake the pieces that don't exist yet:

- **Member 3**, to test Task 6 (cleanup) before Task 5 (spaCy) is fully wired in: hardcode a fake list of raw names like `["Bombay", "Thane"]` and feed that straight into cleanup.
- **Member 3**, to test Task 7 (GeoNames lookup) independently: call it directly with hardcoded cleaned names, no need to wait on cleanup being finished first.
- **You**, to test Task 9 (disambiguation) before Task 7/8 are finished: hardcode a fake candidate list (2-3 fake rows with different populations/coordinates) and confirm the scoring picks the right one and produces a sensible reason string.
- **You**, to test Task 12 (response assembly) before the full pipeline exists: hardcode a fake set of per-name results (mix of resolved and failed) and confirm the JSON it produces matches contract.md exactly.

Integrate for real (plug all pieces together, no more hardcoded fakes) daily if possible — don't wait until the last day to find out two pieces don't actually fit together.

---

## 5. Known Gotchas

- **Nominatim rate limit:** 1 request/second. Also requires a `User-Agent` header identifying the app, or requests may get blocked. Relevant to Task 8 (Member 4) but affects how fast Task 9/12 can run in testing too.
- **`gen_random_uuid()`** in schema.sql needs the `pgcrypto` extension — confirm it's on during Task 1, don't assume.
- **Confidence is always a float 0.0–1.0**, never a 0–100 integer. Keep this consistent across Task 9 (where it's produced) and Task 12 (where it's passed through unchanged).
- **`geonames_alternate_names` fuzzy matching** (Task 6) needs the `pg_trgm` extension enabled — same as above, confirm during Task 1.
- **Per-name caching, not per-sentence:** don't accidentally build a cache check that treats the whole sentence as one unit — Task 10's cache check must be per individual `raw_name`, matching the `resolved_places_cache_lookup` view's `DISTINCT ON (original_text, raw_name)` structure.
- **Order preservation:** Task 12 must return `extracted[]` in the same order names appeared in the original text, even though cached and freshly-resolved names are handled through different code paths internally. Don't let the cache/fresh split scramble the output order.

---

## 6. Versioning

**Current version: v1** — first draft, agreed 9 Aug 2026, aligned with `contract.md` v1 and `schema.sql`.

If pipeline behavior changes (new stage, reordered steps, changed caching granularity), update this doc and `contract.md` together if the change affects response shape, and notify the team.
