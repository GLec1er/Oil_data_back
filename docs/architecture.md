# Architecture notes

Oil Data Back is shaped as a small, inspectable backend foundation. The visual map on the [overview page](index.html) is the short version; this page explains what each boundary is meant to own.

## The flow

```text
field reading → API boundary → validation → async data access → insight
```

### 1. Telemetry source

The product direction starts with time-series readings from wells and field equipment: pressure, temperature, flow rate, and water cut. The interactive lab uses deterministic sample values so the experience is useful before a real data source is connected.

### 2. FastAPI boundary

`app/main.py` creates the application and includes the versioned router from `app/api`. The intended public surface lives under `/api/v1`, keeping future contract changes explicit and reviewable.

### 3. Validation and schemas

`app/api/validators.py` is the natural home for request-level rules. `app/schemas/` is reserved for the shapes exchanged by the API. Keeping validation near the boundary prevents storage details from leaking into the public contract.

### 4. Async data layer

`app/core/db.py` provides an async SQLAlchemy engine, session factory, and declarative base. `app/models/` and `app/crud/` are intentionally small extension points for the first telemetry model and read/write operations.

### 5. Documentation as a product surface

`docs/` is a standalone static site. It has no runtime dependency on FastAPI or PostgreSQL, which makes it safe to publish through GitHub Pages and useful for reviewing the direction of the backend in a browser.

## Design principles

- Keep the API contract versioned from the beginning.
- Prefer async boundaries for ingestion and reads.
- Keep the data model explicit and migration-backed.
- Make the happy path understandable before adding infrastructure.
- Be honest about what is simulated and what is already wired.

## Suggested next slice

1. Define a `TelemetryReading` model with a well identifier and timestamp.
2. Add migrations and an async repository in `app/crud/`.
3. Add `POST /api/v1/readings` and `GET /api/v1/readings` with time-range filters.
4. Replace the browser-only sample generator with a small read-only API client.
