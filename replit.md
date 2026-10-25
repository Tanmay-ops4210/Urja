# UrbanHeat Analytics

An applied data analysis dashboard for exploring documented Mumbai urban-heat observations from user-uploaded CSV files.

## Run & Operate

- `streamlit run app.py --server.port 5000 --server.address 0.0.0.0 --server.headless=true --browser.gatherUsageStats=false` — run the UrbanHeat Analytics dashboard
- `python -m unittest discover -s tests -v` — run focused data-preparation and statistics tests
- `pnpm --filter @workspace/api-server run dev` — run the API server (port 5000)
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from the OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- Required env: `DATABASE_URL` — Postgres connection string

## Stack

- Python 3.13, Streamlit, pandas, NumPy, Plotly
- pnpm workspaces, Node.js 24, TypeScript 5.9
- API: Express 5
- DB: PostgreSQL + Drizzle ORM
- Validation: Zod (`zod/v4`), `drizzle-zod`
- API codegen: Orval (from OpenAPI spec)
- Build: esbuild (CJS bundle)

## Where things live

- `app.py` — Streamlit interface and charts
- `analysis.py` — CSV parsing, validation, and testable analysis functions
- `tests/test_analysis.py` — focused standard-library unit tests
- `requirements.txt` — Python runtime dependencies

## Architecture decisions

- Keep the original uploaded CSV separate from a derived analytical view; retain all rows in downloads.
- Use only local CSV uploads in the initial version; source facts and dataset metadata are documented rather than fetched or inferred.
- Analyze one explicitly selected temperature measure at a time and never combine incompatible heat metrics.

## Product

UrbanHeat Analytics supports a college research project on urban heat inequality in Mumbai. It validates uploaded observations and provides data-derived temperature, date, category, vegetation, and coordinate analyses when the required documented fields are available. Do not add fabricated observations or findings.

## User preferences

_Populate as you build — explicit user instructions worth remembering across sessions._

## Gotchas

- The Streamlit app uses port 5000. Do not start the unused API-server workflow at the same time; it also binds port 5000.

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
