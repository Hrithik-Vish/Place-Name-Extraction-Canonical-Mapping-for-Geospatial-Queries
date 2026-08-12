# PS-09 — Place-Name Extraction & Canonical Mapping

SIH 2026 Internal Hackathon project. Extracts place names from free-text (e.g. disaster/emergency reports) using spaCy, resolves each to a canonical location with coordinates via a local GeoNames gazetteer + Nominatim fallback, and disambiguates between candidates using population, proximity, and regional context — with a human-readable reason for every decision.

## Repo Structure

`docs/` and `backend/` are locked — file names and locations match the task breakdowns in `docs/backend_build.md` and `docs/member4_tasks.md` exactly. Push only into the file matching your task; don't rename, move, or restructure these without checking with the team first, since a bad push here can break what everyone else is building against.

`frontend/src/` past `App.jsx` is NOT locked — that's owned by whoever's building frontend, to structure however works best for them.

```
ps09-place-resolver/
├── docs/
│   ├── contract.md
│   ├── backend_build.md
│   ├── frontend_build.md
│   ├── member4_tasks.md
│   ├── tech_stack.md
│   └── schema.sql
│
├── backend/
│   ├── main.py                  # FastAPI app + /resolve endpoint (Task 4)
│   ├── extraction.py            # spaCy logic (Task 5)
│   ├── cleanup.py                # rapidfuzz logic (Task 6)
│   ├── geonames_lookup.py       # local candidate lookup (Task 7)
│   ├── nominatim_fallback.py    # Member 4 — Task 8
│   ├── disambiguation.py        # your Task 9
│   ├── cache.py                  # cache check + storage write (Task 10)
│   ├── response_assembly.py     # your Task 12
│   ├── errors.py                  # Member 4 — Task 13
│   ├── db.py                      # Supabase/Postgres connection setup
│   ├── requirements.txt         # Python dependencies — see docs/tech_stack.md
│   └── data_loader/
│       └── load_geonames.py     # Member 4 — Task 3, CSV loading script
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── App.jsx
│   │   └── ...                    # rest structured however Member 1/2 decide
│   ├── package.json
│   └── .env.example              # placeholder for VITE_API_BASE_URL
│
├── .gitignore
└── README.md                      # short — what the project is, how to run it, links into docs/
```

**Read `docs/` before writing any code that touches the `/resolve` endpoint or its response shape.** Specifically:

- [`docs/contract.md`](docs/contract.md) — exact request/response shape. Source of truth for both frontend and backend.
- [`docs/backend_build.md`](docs/backend_build.md) — full backend pipeline, task-by-task, owned by User + Member 3.
- [`docs/frontend_build.md`](docs/frontend_build.md) — frontend functional scope and suggested task split.
- [`docs/member4_tasks.md`](docs/member4_tasks.md) — CSV loading, Nominatim fallback, error handling.
- [`docs/tech_stack.md`](docs/tech_stack.md) — exact libraries/tools in use. Don't substitute without updating this doc first.
- [`docs/schema.sql`](docs/schema.sql) — database schema (Supabase/Postgres + PostGIS).

## Running Locally

### Backend
```bash
cd backend
pip install -r requirements.txt
python -m spacy download en_core_web_sm
uvicorn main:app --reload
```
Runs on `http://localhost:8000` by default.

### Frontend
```bash
cd frontend
npm install
cp .env.example .env   # set VITE_API_BASE_URL=http://localhost:8000
npm run dev
```

## Contributing

- Push only to the file(s) that match your assigned task — see `docs/backend_build.md` / `docs/frontend_build.md` / `docs/member4_tasks.md` for ownership.
- If your code and a doc in `docs/` disagree, the doc wins — update the doc first, then your code, and tell the team. See `contract.md` Section 1 for the full rule.
- Never commit `.env` — only `.env.example` should be tracked.
