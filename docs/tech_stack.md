# Tech Stack — PS-09 Place-Name Extraction & Canonical Mapping

## 1. Purpose

This is the definitive list of tools, libraries, and services for this project. Everyone — and any AI assistant helping build a piece — should install and reference exactly what's listed here. Don't substitute a similar-sounding library even if it seems equivalent; several of these choices are load-bearing across `contract.md`, `schema.sql`, and `backend_build.md`, and swapping one out can silently break assumptions those docs already made.

---

## 2. Frontend Stack

| Tool | Role |
|---|---|
| **React + Vite** | Build tool + framework. Fast HMR, instant startup, native support for `VITE_API_BASE_URL` env variables (as specified in `contract.md`'s base URL section). |
| **Tailwind CSS** | Utility-first styling — fast to edit colors, status badges (`"resolved"` vs `"failed"`), and component shells without writing separate CSS stylesheets. |
| **Lucide React** | Icons — status indicators, search/submit buttons, map pin popups, edge-case alert banners. |
| **Framer Motion** (primary) | Animation — custom loaders, spring transitions, state-driven UI (`idle` → `loading` → `success`) without breaking layout. |
| **Lottie React** (`lottie-react`) (alternative) | Use instead of Framer Motion if an animation is designed in After Effects/Rive and exported as a `.json` vector file, rather than built directly in code. |
| **React-Leaflet** (`react-leaflet` + `leaflet`) | Map + pin rendering. Uses free OpenStreetMap tiles — no API key or credit card needed, one less setup step before the demo. |

**State management:** plain React `useState`/`useEffect` — no Redux, Zustand, or other state library. The app is a single-page POST-call-and-render flow; adding a state management library would be unnecessary complexity for this scope.

---

## 3. Backend Stack

| Tool | Role |
|---|---|
| **Python + FastAPI** | API framework. Async endpoints, automatic Swagger UI docs, fast native JSON parsing for the `/resolve` payload, integrates cleanly with spaCy and rapidfuzz. |
| **spaCy** (`en_core_web_sm`) | Place-name extraction (NER) — pretrained model, no training required. |
| **rapidfuzz** | Fuzzy matching — cleans up extracted names and matches known aliases/historical names (e.g. "Bombay" → "Mumbai"). |
| **PostGIS** (Postgres extension) | Geospatial queries and storage — powers the `geom` columns and spatial indexing in `schema.sql`. |
| **GeoPandas** | Geospatial data handling on the Python side, alongside PostGIS. |

---

## 4. Data & Geocoding

| Source | Role |
|---|---|
| **GeoNames India subset** (local, offline) | Primary gazetteer — place names, coordinates, population, admin hierarchy, alternate names. Loaded into `geonames_places` / `geonames_alternate_names` (Member 4's Task 3). |
| **Nominatim** (live API fallback) | Backup lookup when a name isn't found locally. Worldwide search, no API key needed, but has a 1 req/sec rate limit and requires a `User-Agent` header — see `member4_tasks.md` for exact usage. |

---

## 5. Database

| Tool | Role |
|---|---|
| **Supabase** (Postgres + PostGIS enabled) | Hosted database — stores the gazetteer tables and the `resolved_places` cache/results table defined in `schema.sql`. |

---

## 6. Why This Stack Wins For a 5-Minute Demo

1. **Zero API friction** — Leaflet + OpenStreetMap and Nominatim both work with no API key registration, no credit card, nothing that can fail or delay setup right before presenting.
2. **Fast to build, fast to demo** — Vite's HMR and Tailwind's utility classes mean UI changes show up instantly during development; FastAPI's Swagger docs make manual endpoint testing trivial without building a separate test client.
3. **Low complexity where it doesn't matter** — no state management library, no over-engineering on the frontend. Complexity is reserved for where it actually adds value: the disambiguation logic (Task 9) and the animation/interaction layer that sells the demo.

---

## 7. What NOT to Substitute

These choices are referenced directly by other docs — swapping any of them out requires updating those docs too, not just this one:

- **spaCy** — `backend_build.md` Task 5 assumes spaCy's specific NER output format.
- **rapidfuzz** — Task 6 assumes rapidfuzz's specific scoring/matching API.
- **Supabase (Postgres + PostGIS)** — `schema.sql` uses Supabase-specific defaults (e.g. `pgcrypto` for `gen_random_uuid()`); a different Postgres host may not have this enabled by default.
- **React-Leaflet** — explicitly chosen to match `frontend_build.md`'s map rendering section and avoid API-key setup risk during the demo.
- **FastAPI** — `contract.md` and `backend_build.md`'s endpoint behavior (async handling, response shape) are written assuming FastAPI conventions.

If a genuine need to swap something arises mid-build, update this doc and flag it to the team — don't swap silently.

---

## 8. Versioning

**Current version: v1** — first draft, agreed 9 Aug 2026, frontend stack confirmed by Member 1.
