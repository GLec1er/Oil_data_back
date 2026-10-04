"""The spec's acceptance scenario, run in-process against a fake Bronze store."""
import json

import pytest

from pipeline import scenario
from pipeline.bronze import read_bronze
from pipeline.snapshot import materialize, replay
from pipeline.verify import fingerprint, run
from tests.pipeline_helpers import write_bronze


@pytest.fixture
def stores(tmp_path):
    return tmp_path / "bronze", tmp_path / "marts"


def test_baseline_then_outage_recovery_replay(stores, capsys):
    bronze, marts = stores
    offset = write_bronze(bronze, scenario.baseline(), 0, "batch-1.parquet")
    materialize(bronze, marts, "materializer-0000000000")
    assert run(bronze, marts, "baseline") == 0

    write_bronze(bronze, scenario.outage(), offset, "batch-2.parquet")
    materialize(bronze, marts, "materializer-0000000001")
    assert run(bronze, marts, "final") == 0
    settled = fingerprint(marts)

    materialize(bronze, marts, "materializer-0000000001")  # restart, nothing new
    assert fingerprint(marts) == settled

    for _ in range(2):
        replay(bronze, marts)
        assert run(bronze, marts, "final") == 0
        assert fingerprint(marts) == settled
    assert len(read_bronze(bronze)) == 7


def test_verify_exits_nonzero_on_mismatch(stores):
    bronze, marts = stores
    write_bronze(bronze, scenario.baseline(), 0, "batch-1.parquet")
    materialize(bronze, marts, "m-1")
    assert run(bronze, marts, "final") == 1


def test_late_event_corrects_its_original_hour(stores):
    bronze, marts = stores
    offset = write_bronze(bronze, scenario.baseline(), 0, "b1.parquet")
    materialize(bronze, marts, "m-1")
    before = json.loads((marts / "active.json").read_text())["counts"]
    write_bronze(bronze, scenario.outage(), offset, "b2.parquet")
    materialize(bronze, marts, "m-2")
    after = json.loads((marts / "active.json").read_text())["counts"]
    assert before["silver"] == 4 and after["silver"] == 5


def test_uncommitted_files_are_ignored(stores):
    bronze, marts = stores
    write_bronze(bronze, scenario.baseline(), 0, "committed.parquet")
    write_bronze(bronze, scenario.outage(), 4, "orphan.parquet")
    log = bronze / "_spark_metadata"
    log.mkdir()
    (log / "0").write_text(
        "v1\n" + json.dumps({"path": f"file:{bronze}/committed.parquet",
                             "isDir": False, "action": "add"}) + "\n"
    )
    assert len(read_bronze(bronze)) == 4
