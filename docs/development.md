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
make down       # stop, keeping all volumes
```

Publish your own data with `docker compose run --rm cli publish --scenario faults --count 8`
(scenarios: `normal`, `duplicates`, `late`, `v2`, `faults`). Add `-v` to `docker compose down` only when you really want to delete the data.

## Checks

```bash
pip install -r requirements/dev.txt
pytest          # unit tests and the in-process recovery scenario; no Docker needed
ruff check .
```

`tests.yml` runs both on every push. The Pages workflow publishes only `docs/`.

## Publishing the showcase

`.github/workflows/pages.yml` publishes `docs/` on pushes to `main`. In the repository settings, set **Pages → Build and deployment → Source** to **GitHub Actions** once.
