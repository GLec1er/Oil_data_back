import json
import threading
import time

import pytest

from pipeline import snapshot
from pipeline.generator import make_event
from pipeline.snapshot import (
    SnapshotError,
    exclusive,
    publish,
    read_active,
    read_manifest,
)
from pipeline.transform import build_datasets
from tests.pipeline_helpers import NOW


def tables(count=2):
    events = [make_event(1, "W", NOW.replace(minute=m)) for m in range(count)]
    return build_datasets(
        [
            {"value": json.dumps(e).encode(), "topic": "t", "partition": 0, "offset": i}
            for i, e in enumerate(events)
        ]
    )


def test_publish_activates_a_complete_snapshot(tmp_path):
    manifest = publish(tmp_path, "s1", tables())
    assert read_manifest(tmp_path)["snapshot_id"] == "s1"
    assert manifest["counts"]["silver"] == 2
    _, active = read_active(tmp_path)
    assert active["silver"].num_rows == 2


def test_no_active_snapshot_until_first_publish(tmp_path):
    assert read_manifest(tmp_path) is None
    with pytest.raises(SnapshotError):
        read_active(tmp_path)


def test_failed_validation_keeps_previous_snapshot_active(tmp_path):
    publish(tmp_path, "good", tables())
    broken = tables()
    broken["hourly"] = tables(3)["hourly"]  # counts no longer match silver
    with pytest.raises(SnapshotError):
        publish(tmp_path, "bad", broken)
    assert read_manifest(tmp_path)["snapshot_id"] == "good"
    assert not (tmp_path / "snapshots" / "bad").exists()
    assert not list((tmp_path / "staging").iterdir())


def test_retry_of_same_snapshot_id_is_idempotent(tmp_path):
    publish(tmp_path, "s1", tables())
    publish(tmp_path, "s2", tables(3))
    publish(tmp_path, "s1", tables())  # a retried batch re-activates, not rewrites
    assert read_manifest(tmp_path)["snapshot_id"] == "s1"
    assert len(list((tmp_path / "snapshots").iterdir())) == 2


def test_crash_after_rename_before_manifest_is_recoverable(tmp_path):
    publish(tmp_path, "s1", tables())
    (tmp_path / "snapshots" / "s2").mkdir()
    snapshot_dir = tmp_path / "snapshots" / "s2"
    import pyarrow.parquet as pq
    for name, table in tables(3).items():
        pq.write_table(table, snapshot_dir / f"{name}.parquet")
    assert read_manifest(tmp_path)["snapshot_id"] == "s1"  # old data still served
    publish(tmp_path, "s2", tables(3))
    assert read_manifest(tmp_path)["snapshot_id"] == "s2"


def test_old_snapshots_are_pruned(tmp_path, monkeypatch):
    monkeypatch.setattr(snapshot, "SNAPSHOTS_TO_KEEP", 2)
    for index in range(5):
        publish(tmp_path, f"s{index}", tables())
        time.sleep(0.01)
    kept = {p.name for p in (tmp_path / "snapshots").iterdir()}
    assert "s4" in kept and len(kept) == 2


def test_exclusive_lock_serialises_publishers(tmp_path):
    order = []

    def second():
        with exclusive(tmp_path):
            order.append("second")

    with exclusive(tmp_path):
        thread = threading.Thread(target=second)
        thread.start()
        time.sleep(0.2)
        order.append("first")
    thread.join(timeout=5)
    assert order == ["first", "second"]
