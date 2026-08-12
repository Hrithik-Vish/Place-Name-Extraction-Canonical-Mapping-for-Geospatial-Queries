# Member 4 — Build Guide (PS-09)

## 1. Purpose & How to Read This Doc

This covers your 3 backend tasks. These sit alongside your primary role in outreach/PPT/presentation — they're scoped deliberately lighter than the rest of the backend split for that reason.

**This is an MVP for an internal round demo, not a production system.** You'll get roughly 5 minutes to actually show it working live; the rest of the presentation is talking through the idea, architecture, and future scope. So: build these to work reliably for the cases you'll actually demo. Rare edge cases get a one-line mention as a known limitation, not a fully engineered handler.

**Reference docs:**
- `schema.sql` — table structure (needed for Task 3)
- `contract.md` — exact response shape your error handling (Task 13) needs to produce
- `backend_build.md` — full pipeline context; your 3 tasks sit inside a bigger chain owned by User and Member 3. Task 8 sits between their Task 7 and Task 9.

---

## 2. Task 3 — CSV / Data Loading

**What:** Load the GeoNames India subset into the database so Task 7 (local lookup, owned by Member 3) has real data to query against.

**Files you're loading:**
- The main places file from the GeoNames India export (`IN.zip` from geonames.org/export) → goes into `geonames_places`
- The alternate names file (aliases, historical names like "Bombay" → "Mumbai") → goes into `geonames_alternate_names`

**Gotcha:** GeoNames' raw files are **tab-separated, not comma-separated**, and the column order isn't labeled in the file itself — you'll need to check GeoNames' documented column layout (available on their export page) to map columns correctly onto `geonames_places`' fields (name, lat, long, population, feature_class, admin codes, etc.). Don't guess the column order from eyeballing the data.

**Also worth knowing:** the file is large. A single giant INSERT may be slow or hit limits — batch it (e.g. a few thousand rows at a time) rather than loading it all in one shot. Doesn't need to be elegant, just needs to finish without erroring out.

**Input:** Raw GeoNames files, Supabase project + schema already live (User's Task 1/2 done first).

**Output:** `geonames_places` and `geonames_alternate_names` populated with real rows.

**Done when:** Querying for a known place — e.g. `SELECT * FROM geonames_places WHERE name = 'Thane';` — returns a real row with correct lat/long. Same check for an alias in `geonames_alternate_names`.

---

## 3. Task 8 — Nominatim Fallback

**What:** When Member 3's local GeoNames lookup (Task 7) comes back empty for a name, call Nominatim as a live backup so the pipeline still has a shot at resolving it before giving up.

**Decided approach:** worldwide search, no country restriction. Reasoning: the local GeoNames India data should already cover essentially every real Indian place name, so if something isn't matching locally, it's a fair bet it's genuinely not in India — a global Nominatim search still applies its own fuzzy/typo-tolerant matching on top of that, it's just not biased toward India specifically. This does mean a name that exists both in India and elsewhere could occasionally resolve to the non-Indian version — acceptable known limitation for an MVP, not worth engineering around.

**Endpoint:** Nominatim's `/search` endpoint.

**Key params:**
- `q` — the cleaned name string (from Task 6, Member 3's cleanup step)
- `format=json`
- No `countrycodes` param (worldwide, per above)
- Set `limit=1` — you just need the best guess, not a full candidate list, to keep this simple for MVP

**Required header:** `User-Agent` — Nominatim requires a descriptive User-Agent identifying the app (e.g. `"ps09-place-resolver/1.0"`). Requests without one may get blocked.

**Rate limit:** 1 request/second. For a demo with a handful of names in one sentence, this is a minor delay, not a real bottleneck — but don't fire requests in a tight loop without at least a small delay between them if multiple names need fallback in the same request.

**Timeout:** set a short timeout (a few seconds) on the request. If Nominatim doesn't respond in time, treat it the same as "no match found" and let it fall through to a `"failed"` entry — don't let a slow external API hang the whole `/resolve` call.

**Output shape:** normalize whatever Nominatim returns into the same shape a local GeoNames candidate would have, so Task 9 (disambiguation, owned by User) can treat both sources identically:
- name/display name → maps to `canonical`
- lat/lon from Nominatim's response → `lat`/`long`
- mark the source as `"nominatim_fallback"` so it's distinguishable from `"local_geonames"` in the final response

**Input:** A cleaned name string that had zero local candidates.

**Output:** Either one normalized candidate (ready to hand to disambiguation), or nothing (if Nominatim also finds no match or times out — this feeds into Task 13).

**Done when:** Feeding it a name you know isn't in the India dataset (e.g. "Springfield") returns a real candidate from somewhere in the world, and feeding it a nonsense string returns nothing without crashing.

---

## 4. Task 13 — Error Handling

**What:** Make sure the edge cases defined in `contract.md` Section 5 actually produce those exact response shapes when they happen for real, not just in theory.

**The two cases that actually matter for the demo:**

1. **No place names found at all** (contract.md 5.2) — this is mostly Member 3's short-circuit logic (right after his Task 5, spaCy extraction), but worth you double-checking it actually returns the right shape: empty `extracted` array + the `message` field explaining nothing was found.

2. **One name fails to resolve while others succeed** (contract.md 5.3) — this is the one you're most directly responsible for, since it's a direct consequence of your Task 8. When Nominatim also comes back empty or times out, make sure a `"failed"` entry gets constructed correctly: `canonical`, `lat`, `long`, `source` all `null`, `confidence: 0.0`, and a `reason` string that's actually informative (e.g. "No local match found; Nominatim fallback also returned no results" — not just a generic error message).

**Important — this task isn't solo.** Failed entries flow into User's Task 9 (disambiguation) and Task 12 (response assembly) — you're not building this in isolation, you're making sure your piece hands off a clean, correctly-shaped failure to theirs. Worth a quick sync with User once your Task 8 + this error handling is working, to confirm the failed entries look right end-to-end in the real response.

**What NOT to over-build for MVP:** you don't need to handle things like the whole Nominatim service being down for an extended period, malformed/corrupted request bodies, or extremely unusual Unicode place names. If they come up in the live demo, that's a one-line "known limitation, future scope" mention during Q&A — not something to engineer defensively against this week.

**Input:** The pipeline's behavior when extraction is empty, or when a name has no local and no Nominatim match.

**Output:** Responses matching contract.md's documented shapes for both edge cases.

**Done when:** You can trigger both edge cases with real test inputs (a sentence with no locations at all; a sentence with one clearly-fake place name) and the JSON that comes back matches contract.md exactly.

---

## 5. Known Gotchas (relevant to your 3 tasks)

- **GeoNames files are tab-separated**, column order isn't labeled — check GeoNames' documented layout before loading.
- **Nominatim rate limit:** 1 req/sec, and requires a `User-Agent` header or requests may be blocked.
- **Timeouts matter more than perfect accuracy for MVP** — a fast, clean "failed" is better than a slow hang.

---

## 6. Versioning

**Current version: v1** — first draft, agreed 9 Aug 2026, aligned with `contract.md` v1 and `backend_build.md` v1.
