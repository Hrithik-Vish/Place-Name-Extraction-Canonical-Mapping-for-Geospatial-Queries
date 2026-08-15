# PS-09 — Presentation Data (Slides 2-5)

**For: Member 4 & Member 5 (PPT/outreach)**
**From: Hrithik (backend lead, Task 9 + 12)**
**Scope: Content for Slides 2, 3, 4, 5 only. Slide 1 (Title) and Slide 6 (Research & References) are yours to research and fill — see notes at the bottom.**

Format reminder (from the official SIH 2026 template): max 6 slides total including title, PDF only, points/diagrams over paragraphs, can't restructure the slide categories — only fill them in.

---

## SLIDE 2 — Proposed Solution

**One-line problem statement:**
[Place-Name Extraction & Canonical Mapping]
Disaster/incident reports (news, OSINT, field messages) mention place names in free text. Analysts at situational-awareness desks need those names turned into map coordinates fast and *correctly* — including when a name is ambiguous (multiple places share the same name across India) or misspelled. Manual lookup doesn't scale under time pressure; naive geocoding gets ambiguous names wrong silently.

**What we built — the pipeline, in order:**
1. **Extraction (spaCy NER)** — pulls raw place-name spans out of incident text. Pattern-based recognition, not dictionary lookup — this is what lets it catch names it's never seen before.
2. **Cleanup (rapidfuzz)** — fuzzy-matches the raw span against known aliases/historical names (e.g. "Bombay" → "Mumbai") using a gazetteer alias table.
3. **Candidate lookup (local GeoNames India + Nominatim fallback)** — finds every place in India matching the cleaned name. Often more than one candidate for the same name.
4. **Disambiguation (our core algorithm)** — picks the *right* candidate when there are several, and explains why in plain language.
5. **Response assembly** — returns coordinates + a human-readable `reason` string per place, ordered to match the original text.

**How it addresses the problem:**
- Turns unstructured incident text into map-ready coordinates automatically.
- Every resolution comes with an auditable reason — an analyst can see *why* the system picked a location, not just trust a silent black-box pin. This matters specifically for disaster response, where a wrong pin costs real time.
- Handles partial failure gracefully: if one name in a report can't be resolved, the rest of the report still resolves normally (no all-or-nothing failure).

**Innovation & uniqueness (this is the highest-weighted judging parameter — lean on this):**

1. **Two-level caching architecture that gets smarter across unrelated requests.**
   Most systems either re-resolve everything every time, or cache by exact sentence (which barely helps). Ours caches at two levels: (a) exact raw string → instant reuse, even across completely different incident reports, and (b) cleaned/normalized name → reuse even when a *new* misspelling of an already-known place shows up. A place name resolved once, anywhere in the system's history, resolves instantly everywhere after — including in a sentence it's never appeared in before.

2. **Evidence-weighted disambiguation, not population-only guessing.**
   Naive geocoders often just return the largest/most popular place with a given name. Ours treats population as a *prior* (what's statistically likely with zero other evidence) — not the deciding factor. Two other signals outrank it when available:
   - **Proximity to other places already resolved in the same report** (incident reports naturally cluster place names — "flooding in Thane, spreading to Kalyan" — so a small village near an already-confirmed location is more likely correct than a same-named big city far away).
   - **Explicit regional context in the text** ("...in Raigad district", "...Maharashtra officials said...") — wire-report language states this more reliably than casual text.
   A population-only guess (no other evidence available) is deliberately confidence-capped, so the system never presents a low-confidence guess as if it were a confirmed match.

3. **Honest, bounded failure — by design, not by accident.**
   The system is deliberately scoped to India only (GeoNames India + India-scoped Nominatim). A non-Indian name like "Springfield" is expected to fail cleanly, with a `reason` string that says so explicitly — this is a stated product boundary, not a bug. One name failing never breaks the rest of the report's resolution (a single bad API call can't take down the whole response).

**Target user (important framing point):**
This is **not** a citizen-facing app. The user is an analyst/operator at a situational-awareness desk — news/OSINT analysts, government disaster-management ops cells — pasting incident reports and needing fast, trustworthy geolocation. This is infrastructure that sits between raw incident text and the map a real decision gets made on, not a standalone consumer product. [Open flag for Member 4/5 — see note at bottom on how hard to lean into this framing vs. giving it a broader "ultimately helps disaster response" halo.]

---

## SLIDE 3 — Technical Approach

**Tech stack:**

| Layer | Tools |
|---|---|
| Frontend | React + Vite, Tailwind CSS, Lucide React (icons), Framer Motion / Lottie (animation), React-Leaflet (map) |
| Backend | Python + FastAPI |
| NLP / Matching | spaCy (`en_core_web_sm`) for extraction, rapidfuzz for fuzzy alias matching |
| Database | Supabase (Postgres + PostGIS + pg_trgm) |
| Geospatial data | GeoNames India (local gazetteer), Nominatim (live fallback, India-scoped) |
| Deployment | Vercel (frontend, native GitHub integration) |

Why this stack (useful for the "technology-stack advantage" judging point): zero API-key friction (Leaflet/OSM and Nominatim both need no signup or credit card — nothing that can fail right before presenting), fast iteration (Vite HMR, FastAPI's automatic docs), and complexity spent only where it earns its keep — the disambiguation logic and caching design, not unnecessary state-management or infra overhead.

**Pipeline / methodology (for a flowchart — stages in order):**

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

**Two-level cache diagram note for the deck:** worth drawing as two boxes — "raw string cache" (fast, exact match) feeding into "cleaned-name cache" (broader match, still skips the expensive disambiguation step) — with disambiguation only running on a genuine double-miss. This is the piece most worth visualizing since it's also the core novelty claim.

---

## SLIDE 4 — Feasibility and Viability

**Status as of this writing (16 Aug):** flagging plainly so this slide doesn't overclaim — full pipeline is not yet live end-to-end. Architecture, schema, and disambiguation logic (the hardest part) are fully built and reviewed. Data loading, endpoint wiring, and frontend integration are in progress, targeting a live deployed link by this weekend and a complete working prototype by Monday 17 Aug for mentor review, ahead of the 19 Aug demo. [If real pipeline metrics — response times, cache hit rates, resolution accuracy on test cases — exist by the time this slide is finalized, swap them in; they'll land better than the architecture-only framing below.]

**Feasibility:**
- **Technical:** every component (spaCy, rapidfuzz, FastAPI, Supabase/PostGIS, GeoNames India, Nominatim) is free, open-source or has a generous free tier — no paid API keys, no credit card, no vendor lock-in risk before or during the demo.
- **Data:** GeoNames India is a complete, real, offline dataset — no scraping, no synthetic data, no ongoing licensing cost.
- **Architecture already resolved the hard design questions before any code was written** — the two-level cache schema, the disambiguation weighting, and the full request/response contract were all decided and documented up front (worth mentioning as evidence of engineering discipline, not just "we're behind schedule").

**Potential challenges and risks (be upfront — judges reward honesty here over hiding gaps):**
1. **Ambiguous names without any textual evidence.** If a place name appears with zero proximity or regional context (e.g. the very first name in a report), the system falls back to population-only, deliberately confidence-capped. *Mitigation:* the confidence score itself signals "verify this one" to the analyst — it never silently presents a guess as certain.
2. **Extraction depends on spaCy correctly recognizing a span as a place at all.** If spaCy misses a badly garbled or unusually formatted name, cleanup/disambiguation never see it. *Mitigation:* named explicitly as a known limitation, not hidden — honest boundary, not a hidden failure mode.
3. **Nominatim's 1 req/sec rate limit** could slow resolution if many names miss the local gazetteer in a single request. *Mitigation:* the two-level cache means this cost is paid once per unique name, ever — not on every repeat occurrence.
4. **Failed resolutions are deliberately never cached** (a timeout today isn't necessarily a timeout tomorrow) — a known, named trade-off, not an oversight. Caching failures safely needs a TTL/invalidation strategy, explicitly scoped as future work rather than rushed under deadline pressure.

**Scalability / what changes at higher load** (judges may ask this directly — "what changes at 10,000 users?"):
The fast-path cache is the direct answer — most place names in Indian incident reports repeat heavily (major cities, states, districts), so cache hit rate should climb fast with usage, meaning the Nominatim rate-limit bottleneck matters less over time, not more. New/rare names still pay the full pipeline cost once, then are instant for every future request system-wide.

---

## SLIDE 5 — Impact and Benefits

**Target audience:** analysts and operators at situational-awareness / monitoring desks — news and OSINT analysts, government disaster-management operations cells — who currently have to manually cross-reference place names against a map while working from raw incident text under time pressure.

[Open flag for Member 4/5: decide how directly to state this. Option A — lead with the analyst as the explicit user (more honest, more differentiated from every citizen-facing PS in the COMP list, but requires the judge to follow one more inferential step to "why does this matter"). Option B — lead with downstream impact ("faster, more accurate disaster response reaching affected people") and introduce the analyst as *how* that happens. Option B is more emotionally immediate but risks sounding like every other PS in the room. Recommend B for the impact framing, but keep A explicit and central on slide 2 so the technical judges don't think this is a citizen app with a confused pitch.]

**Benefits:**
- **Speed under pressure:** removes manual place-name lookup as a bottleneck during time-critical disaster response — the system does in seconds what would otherwise mean cross-referencing a map by hand while new reports keep coming in.
- **Trust, not just automation:** every resolved location comes with a plain-language reason — analysts can audit *why* the system made a call, not just accept an opaque pin. This matters especially for high-stakes decisions (e.g. where to send rescue resources).
- **Bounded, honest failure:** the system never silently guesses wrong with false confidence — a low-evidence match is flagged as low-confidence, and a genuinely unresolvable name fails cleanly with a clear reason rather than corrupting the response.
- **Reusable infrastructure, not a one-off tool:** as a backend service (not a standalone app), this could plug into other disaster-response or situational-awareness tools that need geolocation from free text — it's the layer between raw reports and any map-based decision tool, not a competitor to them.
- **Improves with use:** the caching architecture means the system gets faster and cheaper (fewer live API calls) the more it's used — impact compounds rather than staying flat.

---

## Notes for Member 4 & Member 5 — your research scope

**Slide 1 (Title):** straightforward — Problem Statement Title is "Space Technology PS-09: Place-Name Extraction & Canonical Mapping for Geospatial Queries," PS Category is Software, Theme is Space Technology (per official registration — yes, it reads oddly for a disaster-response NLP tool, that's just the theme bucket it landed in on the registration form). You'll need a team name — check if one's already been decided; if not, pick something and confirm with Hrithik before finalizing.

**Slide 6 (Research and References):** this is on you to research properly, not just fill with placeholder links. Useful directions:
- Look for any existing published work on toponym resolution / place-name disambiguation (this is the actual academic term for what Task 9 does — worth searching "toponym resolution NLP" or "geoparsing disambiguation").
- GeoNames and Nominatim's own documentation are legitimate references for the data/geocoding layer.
- Worth a quick competitive scan: is there an existing open-source or commercial tool that does something similar (geocoding + disambiguation specifically for disaster/incident text)? If you find one, a short comparison table (like BitRiot's SIH 2025 deck did) is strong evidence for the "USP / differentiation" judging point — but only include it if the comparison is real and accurate, not padded.
