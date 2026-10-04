# Telemetry Pipeline Design

**Status:** Implemented (see `pipeline/`)
**Date:** 2026-10-03

## Purpose and scope

Build a reproducible local portfolio project that turns simulated oil-well telemetry into inspectable analytical data. New events should normally appear in the marts within tens of seconds on a healthy local machine. The demonstration must show duplicates, late events, an additive schema change, historical reprocessing, and correct results after stopping and restarting the processor.

The current repository has a FastAPI and SQLAlchemy shell plus a browser-only telemetry demo. It has no Kafka producer, Spark processor, Parquet store, or analytical mart. The existing demo's measurement names remain the starting vocabulary. This delivery focuses on the data pipeline and a command-line verification report; connecting the static site or HTTP API to the marts can follow as a separate slice.

The local runtime uses a single-node Kafka broker, PySpark in local mode, and persistent local volumes for Parquet and Spark checkpoints. Docker Compose starts the dependencies and processors. Exact compatible image and library versions will be pinned during implementation.

## Event contract

The Kafka topic `telemetry.raw` carries UTF-8 JSON. Its key is `well_id`; the payload contains:

| Field | Rule |
| --- | --- |
| `schema_version` | Required integer: `1` or `2` in this delivery. |
| `event_id` | Required stable, globally unique ID for one measurement. Retries reuse it. |
| `source_id` | Required nonempty producer identifier. |
| `well_id` | Required nonempty well identifier. |
| `event_time` | Required UTC timestamp of the measurement. |
| `emitted_at` | Required UTC timestamp of publication; it is delivery metadata. |
| `pressure_bar` | Required finite number, at least zero. |
| `temperature_c` | Required finite number. |
| `flow_m3_h` | Required finite number, at least zero. |
| `water_cut_pct` | Required finite number between 0 and 100 inclusive. |
| `pump_current_a` | Optional finite nonnegative number, introduced in version 2; null for version 1. |

Unknown versions, malformed JSON, invalid timestamps, and invalid values are recorded as rejected rows with a reason. The raw message is retained even when parsing fails. Version 2 adds only the optional `pump_current_a` field. Silver output always has one explicit canonical schema with this nullable column; readers need not infer or merge arbitrary Parquet schemas.

The deterministic generator accepts a seed, well list, start time, sample count, and scenario. It can publish a normal run and named fault injections. The same logical measurement keeps the same `event_id` across generator retries and replay.

## Data flow and storage

```text
generator → Kafka telemetry.raw
          → Spark raw stream → bronze Parquet
          → Spark materializer stream → versioned silver, rejects, hourly and daily marts
          → active snapshot manifest → verification command
```

1. The raw Spark query reads Kafka and writes append-only Bronze Parquet with a fixed schema: raw payload, topic, partition, offset, Kafka timestamp, and ingestion timestamp. It partitions by ingestion date, so an old `event_time` is still accepted. Its file sink and checkpoint use distinct persistent directories. Kafka's retention must exceed the planned processor outage; events that expire before raw ingestion cannot be reconstructed from Bronze.
2. A second Spark query watches committed Bronze files. Each micro-batch triggers the materializer. For the bounded portfolio fixture, it rereads all committed Bronze data, builds deterministic Silver and mart results, writes them to a new snapshot directory, validates the snapshot, then atomically replaces a small `active.json` manifest on the same local filesystem. This favors clear correction and replay behavior over large-scale throughput. A normal 10-second trigger on each query aims for an update within tens of seconds; it is a demo target, not a strict latency guarantee.
3. Silver has at most one row per `event_id`. Identical measurements with the same ID collapse to one row. Equality compares the canonical `source_id`, `well_id`, `event_time`, and measurement values; it excludes `schema_version`, `emitted_at`, and Kafka metadata. If the same ID has different measurement content, every variant is excluded from Silver and recorded as a conflict, so no arbitrary winner changes between runs. Malformed and unsupported records go to the rejected dataset with their raw coordinates and reason.
4. Marts group by UTC `event_time` and `well_id`: an hourly mart and a daily mart contain unique reading count, average pressure, average temperature, average flow rate, and maximum water cut. Flow rate is not summed as a volume because irregular sampling would make that result misleading. The last five snapshots are retained (`SNAPSHOTS_TO_KEEP`); a reader must open `active.json` and read its files without long pauses. Every snapshot contains its Silver, rejected, and mart datasets under one version; consumers use only the path named by `active.json`.
5. The materializer's `foreachBatch` callback may execute again after a failure. It uses the stable query identity and `batch_id` to recognize an already published snapshot. A crash before manifest replacement leaves the previous snapshot active; a retry completes or safely repeats the new snapshot. Staging directories are never exposed as active data.

The publisher checks that all snapshot Parquet datasets can be read, Silver IDs are unique, and mart reading counts match Silver before changing `active.json`. A failed write or failed validation leaves the previous snapshot active and fails the materializer query for an observable retry. Unknown event versions and invalid records are retained in Bronze and rejected with a reason rather than stopping ingestion. A missing Kafka offset caused by retention or topic deletion fails the raw query visibly; the pipeline must not silently skip it.

Spark documents checkpoint-based recovery and exactly-once file-sink semantics. It documents `foreachBatch` as at least once unless the application makes writes idempotent using `batchId`. See the [Structured Streaming guide](https://spark.apache.org/docs/latest/streaming/apis-on-dataframes-and-datasets.html). Kafka starting offsets apply only to a new streaming query; an existing checkpoint determines the restart position. See the [Kafka integration guide](https://spark.apache.org/docs/latest/streaming/structured-streaming-kafka-integration.html).

## Late events, schema changes, and replay

Every accepted event in Bronze participates in the next complete snapshot, regardless of its age. A late event therefore corrects its original hour and day. No watermark discards historical events in this local design. The cost is a full Bronze scan on each materialization; the documented scale limit of this approach is the size of the local fixture. Partition-scoped rebuilding is a later optimization if needed.

An additive event-schema change modifies the parser and canonical Silver schema, not the fixed raw-stream schema. Materializer changes are deployed by stopping its query, preserving Bronze, rebuilding a fresh snapshot from Bronze, and then starting the new materializer. The raw query and its checkpoint continue unchanged. Incompatible event changes require a new `schema_version` and an explicit parser rather than silent coercion.

A `replay` command takes the same exclusive file lock (`.publish.lock` next to `active.json`) that every materializer publish holds, which pauses the materializer for the duration; it then reads all committed Bronze data with the same pure transformation rules, writes and validates a new versioned snapshot, publishes its manifest, and releases the lock. It never deletes or rewinds the live checkpoint. Running replay twice on unchanged Bronze must yield identical Silver and mart content, although snapshot directory names and publication timestamps differ.

## Verification and acceptance

Tests cover parsing for both versions, malformed inputs, deterministic generation, duplicate IDs, conflicting IDs, event-time grouping, and snapshot publication/retry. An integration scenario runs the actual Kafka and Spark path with a persistent storage volume:

1. Publish four baseline events: three for `NORTH-07` at 10:00, 10:15, and 11:00 UTC (the first two have pressure 80 and 100 bar), and one for `EAST-12` at 10:00 UTC. Wait until Bronze and the active snapshot contain them.
2. Stop the materializer and raw processor without deleting Kafka, Parquet, or checkpoint volumes. Publish a duplicate of the 10:00 event, a version-2 `NORTH-07` event measured at 10:05 UTC with pressure 120 bar, and one malformed JSON message. Restart both processors.
3. Verify that Bronze contains seven Kafka records, Silver contains five unique valid measurements, and rejects contains the malformed record. The `NORTH-07` 10:00–11:00 UTC hourly row contains three readings with average pressure 100 bar; its daily row contains four readings. The late version-2 row has `pump_current_a` populated; version-1 rows have null.
4. Stop and restart the processors again without publishing anything. Verify that the active Silver and mart contents are unchanged and Bronze has no extra Kafka-coordinate rows.
5. Replay from Bronze twice. Verify that each replay produces the same business rows and aggregate values, with no duplicate `event_id` in Silver. Verify that a reader following `active.json` sees only complete snapshots.

The verification command reports observed and expected counts and key aggregates, and exits nonzero on mismatch. It reads the published Parquet snapshot independently of the materializer's transformation code. The README documents one command to start the stack, one to run the scenario, one to verify the result, and one to stop it while preserving data.

## Delivery slices

1. **Raw ingestion:** event contract, deterministic producer, Compose runtime, Kafka topic, raw Spark query, Bronze Parquet, and checkpoint restart test.
2. **Analytics:** canonical parser, duplicate and rejection rules, versioned snapshots, hourly and daily marts, and unit tests.
3. **Recovery demo:** replay command, processor stop/restart scenario, independent result verification, and documentation of the run and its scale limits.
