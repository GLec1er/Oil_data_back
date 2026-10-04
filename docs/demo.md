# Playground guide

The interactive lab on the [overview page](index.html) is a deterministic, client-side preview of the data contract.

## What to try

1. Drag **Pressure**, **Temperature**, **Flow rate**, or **Water cut**.
2. Watch the trend line, health score, and status change together.
3. Switch the well to see the selected `well_id` in the payload.
4. Copy the generated JSON and use it as a conversation starter for the first API schema.

## Why it is simulated

The playground runs entirely in the browser. The real pipeline (Kafka, Spark, Parquet marts) lives in `pipeline/` and is verified from the command line, not from this page: connecting the site to the marts is a later slice. The playground is therefore intentionally transparent: it shows the event contract without fabricating a live connection.

## Sample contract

```json
{
  "schema_version": 2,
  "event_id": "sample-NORTH-07-2026-10-01T10:00:00Z",
  "source_id": "sim-1",
  "well_id": "NORTH-07",
  "event_time": "2026-10-01T10:00:00Z",
  "emitted_at": "2026-10-01T10:00:02Z",
  "pressure_bar": 84.6,
  "temperature_c": 72,
  "flow_m3_h": 128,
  "water_cut_pct": 18
}
```

This is the `telemetry.raw` event contract (see `pipeline/contract.py`). Schema version 2 adds the optional `pump_current_a`; version 1 events omit it and it is stored as null.
