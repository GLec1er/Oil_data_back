# Architecture notes

Oil Data Back has two parts: a small FastAPI shell (`app/`) and a replayable telemetry pipeline (`pipeline/`). The visual map on the [overview page](index.html) is the short version; this page explains what each boundary owns. The full design lives in [`design/specs`](https://github.com/glec1er/Oil_data_back/tree/main/design/specs).

## The data flow

```text
generator → Kafka telemetry.raw
          → Spark raw stream      → Bronze Parquet (append-only, fixed schema)
          → Spark materializer    → versioned snapshot: Silver, rejects, conflicts, hourly + daily marts
          → active.json manifest  → verify command
```

### 1. Event contract (`pipeline/contract.py`)
UTF-8 JSON keyed by `well_id`. Schema version 1 has `event_id`, `source_id`, `well_id`, `event_time`, `emitted_at` and four measurements; version 2 adds the optional `pump_current_a`. Malformed, unsupported or out-of-range events are never dropped: they are rejected with a reason and the raw bytes are kept.

### 2. Bronze (`pipeline/raw_stream.py`)
Spark Structured Streaming copies each Kafka record (value, topic, partition, offset, Kafka timestamp, ingestion time) into Parquet partitioned by ingestion date, so an old `event_time` is still accepted. A missing offset fails the query instead of being skipped.

### 3. Silver, rejects and marts (`pipeline/transform.py`)
A pure function from Bronze rows to datasets. One Silver row per `event_id`; identical repeats collapse, differing repeats are excluded and recorded as conflicts. Hourly and daily marts group by UTC `event_time` and `well_id`. Flow rate is averaged, never summed.

### 4. Snapshots (`pipeline/snapshot.py`)
Every micro-batch rebuilds all datasets from all committed Bronze files, so a late event corrects its original hour and day. The result is validated in a staging directory, renamed to `snapshots/<id>`, and only then exposed by atomically replacing `active.json`. Snapshot ids derive from the Spark `batch_id`, which makes a retried `foreachBatch` idempotent. A file lock serializes the materializer and `replay`.

### 5. Verification (`pipeline/verify.py`)
Reads only Parquet and `active.json` — no transformation code — and exits nonzero if counts or aggregates differ from the expectation.

### 6. FastAPI shell and the static site
`app/` exposes `GET /api/v1/health` and keeps the async SQLAlchemy foundation for a later read API over the marts. `docs/` is a standalone static site published through GitHub Pages.

## Scale limits

Materialization rereads all of Bronze each time. That is deliberate: it favors clear correction and replay semantics for a bounded local fixture. Partition-scoped rebuilds are the next optimization if the data grows. Kafka retention (7 days locally) must exceed any planned processor outage; events that expire before raw ingestion cannot be reconstructed.

## Design principles

- Keep the API contract versioned from the beginning.
- Never silently drop data: reject with a reason or fail visibly.
- Make correction and replay deterministic.
- Be honest about what is simulated and what is wired.
