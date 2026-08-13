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
Create a resolution_requests row (original_text) — position tracking
starts here
        ↓
spaCy extraction — pull every place-name span out of the text
        ↓
For EACH extracted raw_name, individually, IN ORDER:
        ↓
   FAST PATH: Check raw_name_fast_path view for this exact raw_name
        ↓
   ┌─────────────────┴─────────────────┐
   FAST-PATH HIT                   FAST-PATH MISS
   ↓                                     ↓
   Use stored cleaned_name/          rapidfuzz cleanup (normalize spelling,
   canonical/lat/long/               strip noise, match known aliases)
   confidence/reason/source                ↓
   directly — skip cleanup,          Check: does this cleaned_name already
   lookup, AND disambiguation        exist in resolved_places?
   entirely                                ↓
   ↓                                 ┌─────┴─────┐
   ↓                                 YES          NO
   ↓                                 ↓             ↓
   ↓                          Reuse existing   Local GeoNames lookup
   ↓                          resolved_places        ↓
   ↓                          row — write a    Found locally? ──No──→ Nominatim fallback
   ↓                          NEW raw_name_          ↓ Yes                   ↓
   ↓                          aliases row            ↓                  Found? ──No──→
   ↓                          pointing to it          ↓                       ↓
   ↓                          (no fresh                ↓                mark this ONE
   ↓                          resolution needed)        ↓                name "failed"
   ↓                                 ↓             Disambiguation             (not cached —
   ↓                                 ↓             (population,               always retries
   ↓                                 ↓             proximity, region          fresh next time)
   ↓                                 ↓             hints → confidence               ↓
   ↓                                 ↓             + reason)                        ↓
   ↓                                 ↓                   ↓                          ↓
   ↓                                 ↓             Write NEW row to                 ↓
   ↓                                 ↓             resolved_places, THEN            ↓
   ↓                                 ↓             write NEW raw_name_aliases       ↓
   ↓                                 ↓             row pointing to it               ↓
   ↓                                 └─────┬─────────────┘                          ↓
   └─────────────────┬───────────────────────────────────────────────────────────────┘
                      ↓
        Response assembly — combine all resolved (fast-path hits +
        freshly resolved + reused cleaned_name) + failed entries
        into one extracted[] array, using resolution_request_items'
        position_in_text to preserve original order
                      ↓
              Return JSON per contract.md
```

**Key points:**
- **Two-level caching now, not one.** The fast path (`raw_name_aliases`) catches exact repeat raw strings — including across completely different sentences — and skips cleanup, lookup, AND disambiguation. A fast-path miss still has a second chance to avoid re-resolving: if cleanup produces a `cleaned_name` that's already in `resolved_places` (e.g. a new misspelling of a place already resolved before), lookup and disambiguation are skipped too — only a new alias row is written, not a new resolution.
- **Failures are never cached.** A name that fails to resolve (no GeoNames match, no Nominatim match) is not written to `resolved_places` or `raw_name_aliases`. It will always retry the full pipeline fresh if the same raw name appears again. This is a deliberate MVP scope decision — see Known Gotchas.
- **Per-name, not per-sentence**, same as before: if a sentence has 3 names and 1 hits the fast path, only the other 2 run through cleanup/lookup/disambiguation.

**Short-circuit case:** if spaCy finds zero names at all, skip everything after extraction and return immediately per contract.md Section 5.2 (empty `extracted` array + message). No `resolution_request_items` rows are needed in this case since there's nothing to position.

---

## 3. Per-Task Breakdown

### Task 1 — Supabase Project Setup (User)
**What:** Create the Supabase project. Enable the `postgis` and `pg_trgm` extensions. Confirm `pgcrypto` is enabled (needed for `gen_random_uuid()` in schema.sql — usually on by default in Supabase, but verify).
**Input:** None — this is the foundation everything else sits on.
**Output:** A live Supabase project with the right extensions on, and a connection string/API key ready to share with Member 3 and Member 4 (needed for Task 3 — CSV loading).
**Done when:** You can run a test query like `SELECT postgis_version();` and `SELECT * FROM pg_extension;` and see `postgis`, `pg_trgm`, and `pgcrypto` all listed.

### Task 2 — Run schema.sql (User)
**What:** Execute `schema.sql` against the Supabase project to create `geonames_places`, `geonames_alternate_names`, `resolved_places`, `raw_name_aliases`, `resolution_requests`, `resolution_request_items`, and the `raw_name_fast_path` view.
**Input:** The Supabase project from Task 1, `schema.sql`.
**Output:** All tables and the fast-path view exist and are queryable.
**Done when:** All 6 tables + 1 view show up in the Supabase table editor, and the auto-`geom` triggers work — insert a test row with lat/long into `geonames_places` and confirm `geom` populates automatically.

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
**Only runs on a fast-path miss** (Task 10's `raw_name_fast_path` check found nothing, and cleanup's resulting `cleaned_name` also isn't already in `resolved_places`) — a fast-path hit or a reused `cleaned_name` never reaches this task at all.
**Input:** A list of candidates for one name, plus the set of already-resolved names/coordinates from earlier in the same request (for proximity scoring).
**Output:** One chosen candidate (canonical name, lat, long, source) + `confidence` + `reason`. If no candidates exist at all (Task 7 and Task 8 both came back empty), output a `"failed"` entry instead — `canonical`/`lat`/`long`/`source` all `null`, `confidence: 0.0`, `reason` explaining nothing was found. **A failed entry is never written to `resolved_places` or `raw_name_aliases`** — see Task 10 and Known Gotchas.
**Done when:** Feeding it the Thane/Kalyan/Springfield example produces confidence scores and reasons that read sensibly — this is the single most demo-critical piece of logic, since the click-to-reveal "reason" field is what proves the system reasons rather than just retrieves.

### Task 10 — Cache Check + Storage Write (Member 3)
**What:** Three responsibilities folded into one task, run per raw_name:
1. **Fast-path check (first).** Query `raw_name_fast_path` for this exact `raw_name`. If found, use the returned `cleaned_name`/`canonical_name`/`lat`/`long`/`confidence`/`reason`/`source` directly — skip cleanup (Task 6), lookup (Task 7/8), and disambiguation (Task 9) entirely for this name. Optionally bump that `raw_name_aliases` row's `hit_count` and `last_seen_at`.
2. **Second-chance check (on fast-path miss, after cleanup runs).** Once Task 6 produces a `cleaned_name`, check whether that `cleaned_name` already exists in `resolved_places` (unique index on `cleaned_name` makes this a simple lookup). If it does, skip Task 7/8/9 — reuse the existing `resolved_places` row's values, and write a **new** `raw_name_aliases` row linking this `raw_name` to that existing `resolved_places.id`. No new resolution happens.
3. **Fresh write (only if both checks miss).** After a name is freshly resolved via the full pipeline (Task 7/8/9), write **two** rows: a new `resolved_places` row for the new `cleaned_name`, then a new `raw_name_aliases` row linking this `raw_name` to that new `resolved_places.id`. **If the name failed to resolve, write nothing to either table** — no cache entry for failures, always retries fresh next time.

**Input:** The raw name (for both cache checks) or the fully resolved result (for the writes). Failed results are not written anywhere.
**Output:** Either a fast-path hit, a reused-`cleaned_name` hit (with one new alias row), or a fully fresh resolution (with two new rows) — or nothing written at all, on failure.
**Done when:**
- Submitting the same sentence twice — the second time, every name hits the fast path and skips the pipeline entirely (verify via logging/timing).
- Submitting a **different** sentence containing a raw name seen before (even with different surrounding text) also hits the fast path — this is the cross-sentence win the two-level design is for.
- Submitting a new misspelling/variant of an already-resolved place skips lookup/disambiguation (hits the second-chance check) but still writes a new alias row — confirm this via a row appearing in `raw_name_aliases` without a new row appearing in `resolved_places`.
- Submitting a name that fails to resolve, twice — confirm it reruns the full pipeline (including Nominatim) both times, and that no row appears in `resolved_places` or `raw_name_aliases` for it.

### Task 12 — Response Assembly / Final Endpoint Wiring (User)
**What:** Combine the results for every name in the request — whether they came from the fast path, a reused `cleaned_name`, a fresh resolution, or a failure — into the final `extracted[]` array, ordered using `resolution_request_items.position_in_text` (not implicit array order — that ordering now has to be explicitly tracked, since `resolved_places` rows are shared across requests and no longer carry their own per-request position). Wrap with `original_text` (read from the `resolution_requests` row created at the start of the pipeline) and `message` (null in the normal case) per contract.md.
**Input:** A set of per-name results (fast-path hits + reused-`cleaned_name` + freshly resolved + failed), plus the `resolution_requests`/`resolution_request_items` rows for this request.
**Output:** The final JSON response exactly matching contract.md's success-case shape.
**Done when:** The full pipeline, run end to end on the Thane/Kalyan/Springfield sentence, produces JSON that matches contract.md Section 4's example exactly in structure (values will vary slightly based on real data, but field names/types/nesting must match precisely) — and a sentence with names in a scrambled resolution order (e.g. the 3rd name resolves fastest due to a fast-path hit) still comes back in original text order.

### Task 14 — Testing (User)
**What:** Test the full assembled pipeline against a range of inputs: the standard example sentence, a sentence with zero locations (confirms short-circuit), a sentence where one name is real but unfindable (confirms partial-failure shape, and confirms nothing gets cached for it), a repeat submission of the exact same sentence (confirms fast-path caching skips work), and a **different** sentence reusing a raw name from an earlier submission (confirms the fast path works across requests, not just on exact resubmission). Also test a deliberately misspelled variant of an already-resolved place (confirms the second-chance `cleaned_name` reuse path — lookup/disambiguation skipped, but a new `raw_name_aliases` row still gets written). Also sanity-check response times to make sure nothing hangs (especially around Nominatim's rate limit).
**Input:** The fully wired `/resolve` endpoint.
**Output:** A short list of confirmed-working test cases, and a list of any contract mismatches found and fixed before frontend integration.
**Done when:** All 3 edge cases from contract.md Section 5 produce exactly the shapes documented there, verified against real running code, not just read through — plus the cross-sentence fast-path and `cleaned_name`-reuse cases above are confirmed via direct inspection of `resolved_places` and `raw_name_aliases` row counts, not just response timing.

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
- **Nominatim is scoped to India only** (`countrycodes=in` or equivalent) — this was previously worldwide in an earlier draft; see `member4_tasks.md` Task 8 for the current, corrected approach. A non-Indian place name (e.g. "Springfield") is expected to always fail to resolve under this scoping — that's by design, not a bug.
- **`gen_random_uuid()`** in schema.sql needs the `pgcrypto` extension — confirm it's on during Task 1, don't assume.
- **Confidence is always a float 0.0–1.0**, never a 0–100 integer. Keep this consistent across Task 9 (where it's produced) and Task 12 (where it's passed through unchanged).
- **`geonames_alternate_names` fuzzy matching** (Task 6) needs the `pg_trgm` extension enabled — same as above, confirm during Task 1.
- **Two-level caching, not one flat cache:** Task 10's check is (1) `raw_name_fast_path` by exact `raw_name`, then (2) `resolved_places` by `cleaned_name` if the fast path misses. Don't collapse these into a single check — they skip different amounts of work (fast-path hit skips cleanup too; `cleaned_name` reuse still runs cleanup first).
- **Failures are never cached, on purpose.** No row goes into `resolved_places` or `raw_name_aliases` for a failed resolution — every occurrence of an unresolvable name reruns the full pipeline including a fresh Nominatim call. This is a deliberate MVP scope cut (caching failures safely needs a TTL/invalidation strategy, since a timeout today isn't necessarily a timeout tomorrow) — worth mentioning as future scope in the presentation, not something to build under deadline pressure.
- **Dual writes must stay in sync.** A fresh resolution writes to *both* `resolved_places` and `raw_name_aliases` — wrap both writes in a single transaction so a crash between the two can't leave a `raw_name_aliases` row pointing at nothing, or a `resolved_places` row with no alias pointing to it (harmless but wasteful).
- **Order preservation now depends on `resolution_request_items.position_in_text`**, not implicit processing order — Task 12 must read positions from this table rather than assuming results come back in the order they were resolved (a fast-path hit can resolve "instantly" while an earlier name in the sentence is still waiting on Nominatim).

---

## 6. Versioning

**Current version: v2** — introduces `raw_name_aliases` fast-path caching, `resolution_requests`/`resolution_request_items` for ordering, drops failure-caching. Aligned with `contract.md` v1 (unchanged — response shape unaffected) and `schema.sql` v2.

If pipeline behavior changes (new stage, reordered steps, changed caching granularity), update this doc and `contract.md` together if the change affects response shape, and notify the team.
