# Development notes

## Run the backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The database settings are read from environment variables in `app/core/config.py`. For a local PostgreSQL-backed run, provide `POSTGRES_HOST`, `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD`.

> Current snapshot: `app/api/routers.py` calls `include_router()` without a concrete endpoint router, so `uvicorn` will raise during import until the first API router is added. This docs-only pass leaves that backend behavior untouched.

## Run the showcase

The showcase is plain HTML, CSS, and JavaScript. No build step is required:

```bash
python3 -m http.server 8080 --directory docs
```

Open `http://localhost:8080` and use the **Playground** section.

## Project checks

```bash
pytest
flake8 app tests
```

The GitHub Pages workflow publishes only `docs/`. Backend tests and linting remain separate from the static showcase so the public page stays fast and dependency-free.

## Publishing

`.github/workflows/pages.yml` publishes the `docs/` directory on pushes to `main`. In the repository settings, set **Pages → Build and deployment → Source** to **GitHub Actions** once, then the workflow will own future deployments.
