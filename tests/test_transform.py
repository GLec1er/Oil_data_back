import json
from datetime import datetime, timedelta, timezone

from pipeline.generator import iso, make_event
from pipeline.transform import build_datasets
from tests.pipeline_helpers import NOW

T0 = datetime(2026, 10, 1, 10, tzinfo=timezone.utc)


def rows(*events, raw=()):
    values = [json.dumps(e).encode() for e in events] + list(raw)
    return [
        {"value": v, "topic": "t", "partition": 0, "offset": i}
        for i, v in enumerate(values)
    ]


def test_identical_duplicates_collapse_to_one_row():
    event = make_event(1, "W", T0)
    later = {**event, "emitted_at": iso(T0 + timedelta(hours=1)), "schema_version": 2}
    data = build_datasets(rows(event, later))
    assert data["silver"].num_rows == 1
    assert data["conflicts"].num_rows == 0
    assert data["hourly"].column("readings").to_pylist() == [1]


def test_conflicting_variants_are_all_excluded():
    event = make_event(1, "W", T0)
    data = build_datasets(rows(event, {**event, "pressure_bar": 99.9}))
    assert data["silver"].num_rows == 0
    assert data["conflicts"].num_rows == 2


def test_result_is_independent_of_arrival_order():
    events = [make_event(1, "W", T0 + timedelta(minutes=m)) for m in (0, 5, 10)]
    forward = build_datasets(rows(*events))
    backward = build_datasets(list(reversed(rows(*events))))
    assert forward["hourly"].equals(backward["hourly"])
    assert forward["silver"].equals(backward["silver"])


def test_rejects_keep_raw_message_and_coordinates():
    data = build_datasets(rows(raw=[b"{broken"]))
    reject = data["rejects"].to_pylist()[0]
    assert reject["raw"] == b"{broken"
    assert reject["reason"] == "malformed json"
    assert reject["kafka_offset"] == 0


def test_hourly_and_daily_group_by_event_time_not_arrival():
    events = [
        make_event(1, "W", T0, pressure_bar=80.0, flow_m3_h=100.0, water_cut_pct=10),
        make_event(1, "W", T0 + timedelta(minutes=30), pressure_bar=100.0,
                   flow_m3_h=120.0, water_cut_pct=30),
        make_event(1, "W", T0 + timedelta(hours=1), pressure_bar=60.0),
        make_event(1, "W", T0 - timedelta(days=1)),
    ]
    data = build_datasets(rows(*events))
    hourly = {r["hour_start"].hour: r for r in data["hourly"].to_pylist()
              if r["hour_start"].day == 1}
    assert hourly[10]["readings"] == 2
    assert hourly[10]["avg_pressure_bar"] == 90.0
    assert hourly[10]["avg_flow_m3_h"] == 110.0
    assert hourly[10]["max_water_cut_pct"] == 30
    assert hourly[11]["readings"] == 1
    daily = {r["day_start"].day: r["readings"] for r in data["daily"].to_pylist()}
    assert daily == {1: 3, 30: 1}


def test_duplicate_kafka_coordinates_are_counted_once():
    event = make_event(1, "W", T0)
    one = rows(event)
    data = build_datasets(one + one)
    assert data["silver"].num_rows == 1


def test_silver_has_canonical_nullable_pump_column():
    v1 = make_event(1, "W", T0)
    v2 = make_event(1, "W", T0 + timedelta(minutes=5), schema_version=2)
    silver = build_datasets(rows(v1, v2))["silver"].to_pylist()
    assert [r["pump_current_a"] is None for r in silver] == [True, False]


def test_empty_input_produces_all_empty_tables():
    data = build_datasets([])
    assert all(table.num_rows == 0 for table in data.values())
    assert NOW
