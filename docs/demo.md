# Playground guide

The interactive lab on the [overview page](index.html) is a deterministic, client-side preview of the data contract.

## What to try

1. Drag **Pressure**, **Temperature**, **Flow rate**, or **Water cut**.
2. Watch the trend line, health score, and status change together.
3. Switch the well to see the selected `well_id` in the payload.
4. Copy the generated JSON and use it as a conversation starter for the first API schema.

## Why it is simulated

The repository currently contains the FastAPI application shell and async database foundation, but not a production telemetry endpoint. The playground is therefore intentionally transparent: it demonstrates the intended user experience without fabricating a live connection.

## Sample contract

```json
{
  "well_id": "NORTH-07",
  "pressure_bar": 84.6,
  "temperature_c": 72,
  "flow_m3_h": 128,
  "water_cut_pct": 18
}
```

The field names are compact and transport-friendly. The final schema can add a timestamp, source identifier, quality flag, and units metadata when ingestion is implemented.
