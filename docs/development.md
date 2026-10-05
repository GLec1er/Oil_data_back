# Development notes

## Run the API shell

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements/dev.txt
cp .env.example .env
uvicorn app.main:app --reload
```

`GET /api/v1/health` returns `{"status": "ok"}`. Database settings come from `POSTGRES_*` variables (see `.env.example`); `.env` is git-ignored.

## Run the pipeline

Docker Compose runs Kafka (KRaft), the raw Spark query and the materializer. Data survives restarts in the `kafka-data` and `pipeline-data` volumes.

```bash
make up         # start the stack
make scenario   # duplicates, late v2 event, malformed input, restarts, two replays
make verify     # compare the active snapshot with the expected result
make replay     # rebuild the marts from Bronze
make api        # read API on http://localhost:8000 (API_PORT=8010 make api for another port)
make down       # stop, keeping all volumes
```

Publish your own data with `docker compose run --rm cli publish --scenario faults --count 8`
(scenarios: `normal`, `duplicates`, `late`, `v2`, `faults`). Add `-v` to `docker compose down` only when you really want to delete the data.

## Read API

The API reads the published marts through `active.json` from a read-only mount of the pipeline volume. Locally, set `MARTS_DIR` to a marts directory.

| Endpoint | Purpose |
| --- | --- |
| `GET /api/v1/snapshot` | Active snapshot id, publication time, row counts |
| `GET /api/v1/wells` | Wells present in the marts |
| `GET /api/v1/marts/{hourly\|daily}` | Mart rows; filters `well_id`, `start` (inclusive), `end` (exclusive), paging `limit` (1–1000, default 100) and `offset` |

Rows are ordered by period then well. Naive timestamps are read as UTC. Every response carries the `snapshot_id` it was read from, so a client can tell whether two reads saw the same data. Before the first snapshot is published the API answers `503` with `Retry-After: 15`. Interactive docs: `/docs`.

```bash
curl "localhost:8000/api/v1/marts/hourly?well_id=NORTH-07&start=2026-10-01T00:00:00Z"
```

## Connect the site to the API

The **Live data** section of the showcase reads the API from the browser, refreshes every 15 seconds and shows the hourly or daily marts of one well. It falls back to a plain message when the API is unreachable, and the playground above it always stays a simulation.

```bash
make up && make api                                           # pipeline + API on :8000
docker compose run --rm cli publish --scenario normal --count 96   # a day of data for two wells
python3 -m http.server 8080 --directory docs                  # the site
```

Open `http://localhost:8080/#live`. Use another API address with the **Connect** field or `?api=http://localhost:8010`; an address you type is remembered in `localStorage` once it connects, an `?api=` value never is.

Browsers only let a page read the API when its origin is allowed. `CORS_ORIGINS` (comma separated) defaults to `http://localhost:8080`, `http://127.0.0.1:8080` and `https://glec1er.github.io`; set it when the site runs on another port. Only `GET` is allowed.

> **The published GitHub Pages site** is HTTPS and static, so it can only reach an API you run yourself: Chrome allows an HTTPS page to call `http://localhost` after a local-network permission prompt, Safari blocks it as mixed content. For a reliable demo, serve the site locally as above, or put the API behind HTTPS and enter its address.

## Checks

```bash
pip install -r requirements/dev.txt
pytest              # unit tests, API tests and the in-process recovery scenario; no Docker needed
node --test tests/js   # the site's pure helpers (Node 20+)
ruff check .
```

`tests.yml` runs both on every push. The Pages workflow publishes only `docs/`.

## Publishing the showcase

`.github/workflows/pages.yml` publishes `docs/` on pushes to `main`. In the repository settings, set **Pages → Build and deployment → Source** to **GitHub Actions** once.
