# Frontend Build Guide — PS-09 Place-Name Extraction & Canonical Mapping

## 1. Purpose & How to Read This Doc

Task division for frontend is being handled within the frontend team itself. This doc isn't a fixed task assignment — it's the full functional scope of what the frontend needs to do, plus a suggested starting split (Section 4) as a jumping-off point, not a mandate.

**This is an MVP for an internal round demo, not a production system.** You'll get roughly 5 minutes to show it working live — prioritize the core flow working cleanly over polish, animations, or responsiveness edge cases. See Section 6.

**Reference doc:** `contract.md` is the exact source of truth for the request/response shape. Read it before wiring up the fetch call — this doc summarizes the essentials but isn't a substitute for it.

---

## 2. Functional Scope — What The Frontend Needs To Do

- **Text input** — a box for the user to type or paste a sentence.
- **Frontend-side empty/whitespace validation** — before sending anything, check the trimmed input isn't empty. If it is, block submission and show an inline message (e.g. "Please enter some text before submitting"). **The backend is never called in this case** — this logic must live here, not on the backend (see contract.md Section 5.1).
- **Call `POST /resolve`** with `{ "text": "..." }` once validation passes.
- **Render the response**, which includes:
  - The original text, with extracted place names visually highlighted/underlined
  - A results list or table of extracted places
  - A map (Leaflet or equivalent) with a pin for each successfully resolved place, positioned at its `lat`/`long`
- **Click-to-reveal interaction** — clicking a highlighted name, a pin, or a results-list entry should reveal that place's `reason` field. **This is the single most important interaction for the demo** — it's what shows the system is reasoning about disambiguation, not just doing a database lookup. Prioritize this working smoothly over anything else visual.
- **Handle "no locations found" state** (contract.md Section 5.2) — when `extracted` comes back as an empty array, show a clear message instead of an empty map with no explanation.
- **Handle partial failures within a response** (contract.md Section 5.3) — an entry with `"status": "failed"` should render differently from a resolved one. Doesn't need to be elaborate — a greyed-out list entry or a small "couldn't resolve" tag next to that name is enough. No pin gets placed for a failed entry (no lat/long exists for it).

---

## 3. Contract Reference (Condensed)

Full detail is in `contract.md` — this is just enough to start building against.

**Request:**
```json
{ "text": "Flood reported near Thane, spreading toward Kalyan. Springfield authorities also on alert." }
```

**Response (success case, top level):**
```json
{
  "original_text": "...",
  "extracted": [ /* array of place objects, can be empty */ ],
  "message": null
}
```

**Each item in `extracted`:**
| Field | Type | Notes |
|---|---|---|
| `raw` | string | exact text span extracted |
| `canonical` | string \| null | resolved name, `null` if failed |
| `lat` / `long` | float \| null | `null` if failed |
| `confidence` | float 0.0–1.0 | `0.0` if failed |
| `reason` | string | always present — this is the click-to-reveal content |
| `source` | string \| null | `"local_geonames"` / `"nominatim_fallback"` / `null` |
| `status` | string | `"resolved"` or `"failed"` — use this to decide pin vs. no-pin rendering |

---

## 4. Suggested Starting Split

Offered as a starting point, not a fixed assignment — adjust however makes sense once you're in it.

**Option A — by layer:**
- Input handling + validation + the fetch call + rendering the results list/highlighted text
- Map integration + pin rendering + the click-to-reveal interaction

**Option B — by state:**
- The "happy path" — normal input, normal successful response, full results + map rendering
- Edge case states — empty-input validation, no-locations-found message, partial-failure rendering for individual failed entries

Either split (or a mix) works fine — the two halves aren't fully independent (edge case UI still needs the same results components as the happy path), so some coordination either way is expected regardless of how it's divided.

---

## 5. Local Dev Note — Building Before Backend Is Live

No need to wait on the backend being fully wired up. Since `contract.md` defines the exact response shape, you can hardcode a fake response matching it — including a fake `"failed"` entry and a fake empty-`extracted` response — and build/test all the UI states against those mocks. Swap in the real `fetch` call to `/resolve` once the backend's ready; if the UI was built against the contract shape correctly, nothing else should need to change.

---

## 6. MVP Scope Note

5 minutes of live demo time, rest of the presentation is talking. Prioritize in this order:
1. The core flow working reliably (input → submit → results + map show up correctly)
2. The click-to-reveal reason interaction working smoothly — this is the moment that sells the idea
3. The two edge-case states (no locations found, partial failure) rendering distinctly, even simply
4. Visual polish, animations, responsive layout — nice to have, not worth spending scarce time on this week

If something doesn't get fully handled, it's fine to mention it as a known limitation / future scope during the presentation rather than trying to engineer around it under time pressure.

---

## 7. Versioning

**Current version: v1** — first draft, agreed 9 Aug 2026, aligned with `contract.md` v1.
