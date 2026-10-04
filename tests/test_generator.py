import json
from datetime import datetime, timezone

import pytest

from pipeline.generator import SCENARIOS, generate

START = datetime(2026, 10, 1, tzinfo=timezone.utc)


def test_same_seed_gives_identical_messages():
    first = generate(3, ["A", "B"], START, 5, "normal")
    assert first == generate(3, ["A", "B"], START, 5, "normal")
    assert first != generate(4, ["A", "B"], START, 5, "normal")


def test_event_ids_are_stable_and_unique():
    ids = [json.loads(v)["event_id"] for _, v in generate(3, ["A", "B"], START, 5)]
    assert len(ids) == len(set(ids)) == 10


def test_keys_are_well_ids():
    assert {k for k, _ in generate(1, ["A", "B"], START, 2)} == {"A", "B"}


def test_duplicates_reuse_event_id():
    ids = [json.loads(v)["event_id"] for _, v in generate(1, ["A"], START, 6, "duplicates")]
    assert len(ids) > len(set(ids))


def test_v2_scenario_contains_pump_current():
    payloads = [json.loads(v) for _, v in generate(1, ["A"], START, 4, "v2")]
    assert any(p["schema_version"] == 2 and "pump_current_a" in p for p in payloads)


def test_unknown_scenario_fails():
    with pytest.raises(ValueError):
        generate(1, ["A"], START, 1, "nope")


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_every_scenario_is_deterministic(scenario):
    assert generate(2, ["A"], START, 8, scenario) == generate(2, ["A"], START, 8, scenario)
