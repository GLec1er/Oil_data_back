"""Fixed Parquet schemas for Bronze, Silver, rejects, conflicts and marts."""
import pyarrow as pa

UTC = "UTC"
TS = pa.timestamp("us", tz=UTC)

BRONZE = pa.schema(
    [
        ("value", pa.binary()),
        ("topic", pa.string()),
        ("partition", pa.int32()),
        ("offset", pa.int64()),
        ("kafka_timestamp", TS),
        ("ingested_at", TS),
    ]
)

SILVER = pa.schema(
    [
        ("event_id", pa.string()),
        ("source_id", pa.string()),
        ("well_id", pa.string()),
        ("event_time", TS),
        ("emitted_at", TS),
        ("schema_version", pa.int32()),
        ("pressure_bar", pa.float64()),
        ("temperature_c", pa.float64()),
        ("flow_m3_h", pa.float64()),
        ("water_cut_pct", pa.float64()),
        ("pump_current_a", pa.float64()),
        ("kafka_partition", pa.int32()),
        ("kafka_offset", pa.int64()),
    ]
)

REJECTS = pa.schema(
    [
        ("reason", pa.string()),
        ("raw", pa.binary()),
        ("topic", pa.string()),
        ("kafka_partition", pa.int32()),
        ("kafka_offset", pa.int64()),
    ]
)

CONFLICTS = pa.schema(
    [
        ("event_id", pa.string()),
        ("raw", pa.binary()),
        ("topic", pa.string()),
        ("kafka_partition", pa.int32()),
        ("kafka_offset", pa.int64()),
    ]
)


def _mart(period_field: str) -> pa.Schema:
    return pa.schema(
        [
            (period_field, TS),
            ("well_id", pa.string()),
            ("readings", pa.int64()),
            ("avg_pressure_bar", pa.float64()),
            ("avg_temperature_c", pa.float64()),
            ("avg_flow_m3_h", pa.float64()),
            ("max_water_cut_pct", pa.float64()),
        ]
    )


HOURLY = _mart("hour_start")
DAILY = _mart("day_start")

TABLE_SCHEMAS = {
    "silver": SILVER,
    "rejects": REJECTS,
    "conflicts": CONFLICTS,
    "hourly": HOURLY,
    "daily": DAILY,
}
