# Oil_data_back

> Async-first foundation for turning oil-field telemetry into clean, readable data products.

[![Open interactive showcase](https://img.shields.io/badge/Interactive_showcase-open-F4B860?style=flat-square&labelColor=13202B)](https://glec1er.github.io/Oil_data_back/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-7DD3FC?style=flat-square&labelColor=13202B&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-async-ready-98D8C8?style=flat-square&labelColor=13202B&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)

Oil Data Back is a compact backend playground for an oil-data service. The repository keeps the core intentionally small: FastAPI at the edge, async SQLAlchemy for persistence, Alembic for migrations, and a static visual lab that explains the direction of the project.

## Interactive showcase

The [GitHub Pages showcase](https://glec1er.github.io/Oil_data_back/) is the quickest way to understand the repository. It includes:

- an interactive signal explorer with pressure, temperature, flow, and water-cut controls;
- a deterministic sample payload generator with copy-to-clipboard;
- a visual architecture map for the current backend layers;
- a responsive, dependency-free interface that works as a static GitHub Pages site.

The playground is deliberately a front-end simulation. It makes the product direction visible without pretending that production telemetry already exists.

## Current foundation

| Layer | Role | Status |
| --- | --- | --- |
| FastAPI | HTTP application shell and OpenAPI surface | Foundation |
| `app/api` | Versioned router and validation boundary | Growing |
| SQLAlchemy async | PostgreSQL-ready data access | Foundation |
| Alembic | Schema migration workflow | Wired |
| Docker | Reproducible runtime image | Included |
| `docs/` | Interactive project showcase | Ready |

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

> Note: the current backend snapshot still needs a concrete endpoint router in `app/api/routers.py` before the application can boot. The static showcase is independent from this and works without the backend or a database.

The interactive documentation does not require Python or a database:

```bash
python3 -m http.server 8080 --directory docs
```

Then open `http://localhost:8080`.

## Project map

```text
app/
├── api/          # versioned HTTP boundary and validators
├── core/         # settings, database engine, shared base
├── crud/         # data-access operations (next layer to expand)
├── models/       # SQLAlchemy models
└── schemas/      # API schemas
alembic/          # migrations configuration
tests/            # pytest suite
docs/             # interactive GitHub Pages showcase
```

## Documentation

- [Interactive overview](docs/index.html)
- [Architecture notes](docs/architecture.md)
- [Playground guide](docs/demo.md)
- [Development notes](docs/development.md)

## Direction

The next useful slice is a real telemetry contract: a time-series model, ingestion endpoint, filtering by well and time range, and a small read API that can feed the visual lab. The docs keep this roadmap explicit so the repository is easy to review and easy to extend.

## License

No license has been selected yet. Add one before publishing this project for reuse.
