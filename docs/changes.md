# Changes — v1 → v2 (Caching Redesign + India-Only Nominatim)

## Why this changed

The original cache design keyed on `(original_text, raw_name)` — a name only hit
the cache if the *exact same sentence* was resubmitted. That meant the same
place name appearing in two different sentences ("Flooding in Thane" and
"Heavy rain in Thane district") would resolve fresh, and call Nominatim, both
times.

The new design fixes this with two changes:

1. **A dedicated fast-path table (`raw_name_aliases`)** so any raw string ever
   extracted — across *any* past request — is cached and reusable, not just
   exact sentence resubmissions.
2. **India-only Nominatim scoping**, replacing the earlier worldwide-search
   decision in `member4_tasks.md`, so fallback results can't silently resolve
   to a same-named place in another country.

Separately, an intermediate design (caching *failed* resolutions too) was
considered and **deliberately dropped** for MVP scope — see "What we chose
not to build" below.

**Database is being rebuilt from scratch** (`schema.sql` drops and recreates
everything) — this is not a migration, run it against a clean Supabase
project.

---

## Files changed

| File | What changed |
|---|---|
| `schema.sql` | Full rebuild — new tables, restructured `resolved_places`, new fast-path view |
| `backend_build.md` | Pipeline diagram rewritten, Tasks 2/9/10/12/14 updated, Known Gotchas updated |
| `member4_tasks.md` | Task 8 switched from worldwide to India-only Nominatim, Task 13 wording updated |
| `contract.md` | **No change** — response shape sent to frontend is identical |
| `frontend_build.md` | **No change** — frontend only consumes the response shape, unaffected |

---

## `schema.sql` — what's different

- **`resolved_places`** is now keyed by `cleaned_name` (unique), not by
  `(original_text, raw_name)`. It no longer stores `raw_name` or
  `original_text` at all — it's purely "this cleaned name resolves to this
  canonical place," shared across every request that ever produces that
  cleaned name.
- **New table: `raw_name_aliases`** — maps every raw string spaCy has ever
  extracted (e.g. `"Bombay"`, `"bombay "`, `"Springfield"`) to the
  `resolved_places` row it resolved to. This is the fast-path lookup table.
- **New view: `raw_name_fast_path`** — joins the two above. This is the
  *first* thing the backend checks for any incoming raw name.
- **New tables: `resolution_requests` + `resolution_request_items`** — since
  `resolved_places` no longer stores `original_text` or per-request order,
  something has to. Every `/resolve` call creates one `resolution_requests`
  row, and one `resolution_request_items` row per extracted name recording
  its position in the original text. This is what lets the final response
  come back in the right order even when names resolve out of order (a
  fast-path hit is instant; a fresh Nominatim call isn't).
- **Failed resolutions are not stored anywhere.** No table, no row, for a
  name that fails to resolve. Every occurrence reruns the full pipeline
  fresh — see "What we chose not to build" below.
- Old `resolved_places_cache_lookup` view is gone, replaced by
  `raw_name_fast_path`.

---

## Pipeline — what's different (affects Tasks 6, 7, 9, 10, 12 in `backend_build.md`)

**Old flow, per name:**
1. Check cache by `(original_text, raw_name)`
2. Miss → cleanup → GeoNames/Nominatim → disambiguation → write one row

**New flow, per name:**
1. **Fast-path check** — look up `raw_name` in `raw_name_fast_path`. Hit →
   use cached values directly, skip cleanup/lookup/disambiguation entirely.
2. **Miss →** run cleanup (Task 6) to get `cleaned_name`.
3. **Second check** — does this `cleaned_name` already exist in
   `resolved_places`? Hit → skip GeoNames/Nominatim/disambiguation, reuse
   the existing resolution, write **only** a new `raw_name_aliases` row.
4. **Miss →** run the full pipeline (GeoNames → Nominatim fallback →
   disambiguation). On success, write **two** rows: a new `resolved_places`
   row and a new `raw_name_aliases` row, in one transaction. On failure,
   write nothing.

**Net effect:** the cache now gets *stronger with unrelated use* — a place
name resolved once in any past request is instant everywhere after that, not
just on exact sentence resubmission. Cleanup only runs on an actual cache
miss (fast-path hit skips it too), so hot-path performance is better, not
just cache coverage.

**Order preservation changed mechanism:** the response must be assembled
using `resolution_request_items.position_in_text`, not assumed processing
order — because a fast-path hit can now finish before an earlier name in the
same sentence that's still waiting on a live Nominatim call.

---

## Nominatim scoping — what's different (Task 8 in `member4_tasks.md`)

- **Old:** worldwide search, no country restriction.
- **New:** `countrycodes=in` — India only.
- **Why:** keeps the system's entire geographic scope consistent (GeoNames
  data is India-only; Nominatim fallback should be too) and avoids a
  same-named foreign place being confidently returned as if it were the
  correct Indian location.
- **Visible effect:** a name like "Springfield" will now always return
  `"status": "failed"` — this is expected, not a bug. The `reason` string
  for such failures should say so explicitly (e.g. "No local match; India-
  scoped Nominatim fallback also returned no results") so it reads as a
  deliberate boundary if a judge tests it, not an error.

---

## What we chose not to build (and why)

**Caching failed resolutions** was considered as a further optimization —
same idea as `raw_name_aliases`, but for names that fail to resolve, so a
known-unresolvable name wouldn't retry Nominatim every time.

**Dropped for MVP** because it introduces a real problem plain caching
doesn't have: a Nominatim timeout today isn't necessarily a timeout
tomorrow (network blip, temporary block, etc.), so caching a failure
indefinitely risks permanently marking a real place as "unresolvable" after
one bad network moment. Solving that properly needs a TTL/invalidation
strategy, which isn't worth building under hackathon deadline pressure for
an MVP demo. Worth mentioning as a **named future-scope item** in the
presentation, not something anyone needs to build this week.

**Practical consequence for testing:** if you test the same unresolvable
name twice, expect it to take the same amount of time both times (including
the Nominatim round-trip) — that's expected, not a caching bug.

---

## What every team member needs to know

- **Member 3 (Task 10):** your cache-check logic is now two checks, not one,
  and a fresh resolution is now two writes, not one — see the rewritten
  Task 10 in `backend_build.md`.
- **Member 4 (Task 8):** Nominatim call needs `countrycodes=in` added, and
  your test expectations for "Springfield"-style names have flipped (should
  now fail, not succeed) — see the rewritten Task 8 in `member4_tasks.md`.
- **User/me (Task 9, 12):** disambiguation logic itself (Task 9) is
  unchanged — same scoring factors, same output shape — it just runs less
  often now, only on a genuine double-miss. Task 12 needs to read order
  from `resolution_request_items` instead of assuming array order.
- **Everyone:** `contract.md` — the actual request/response JSON the
  frontend depends on — has not changed at all. Frontend work is
  unaffected by any of this.

---

**Version:** v2, agreed [fill in date when merged]. Supersedes v1 of
`schema.sql`, `backend_build.md`, and `member4_tasks.md`.
