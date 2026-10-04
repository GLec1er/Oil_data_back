"""Independent verification of the active snapshot.

Reads only Parquet files and active.json; it shares no transformation code
with the materializer.
"""
import hashlib
import json
from pathlib import Path

import pyarrow.parquet as pq

from pipeline.bronze import committed_files
from pipeline.scenario import EXPECTED


def _rows(directory: Path, name: str) -> list[dict]:
    return pq.read_table(directory / f"{name}.parquet").to_pylist()


def fingerprint(root: Path) -> str:
    """Hash of business content; ignores snapshot ids, timestamps of publication."""
    manifest = json.loads((root / "active.json").read_text())
    directory = root / manifest["path"]
    content = {
        name: sorted(_rows(directory, name), key=lambda r: json.dumps(r, default=str))
        for name in ("silver", "rejects", "conflicts", "hourly", "daily")
    }
    return hashlib.sha256(json.dumps(content, default=str).encode()).hexdigest()


def bronze_count(bronze_dir: Path) -> int:
    coordinates = set()
    for path in committed_files(bronze_dir):
        table = pq.ParquetFile(path).read(columns=["topic", "partition", "offset"])
        coordinates.update(
            (r["topic"], r["partition"], r["offset"]) for r in table.to_pylist()
        )
    return len(coordinates)


def observe(bronze_dir: Path, root: Path) -> dict:
    manifest = json.loads((root / "active.json").read_text())
    directory = root / manifest["path"]
    silver = _rows(directory, "silver")
    hourly = _rows(directory, "hourly")
    daily = _rows(directory, "daily")
    north_hour = next(
        (
            r
            for r in hourly
            if r["well_id"] == "NORTH-07" and r["hour_start"].hour == 10
        ),
        None,
    )
    return {
        "bronze": bronze_count(bronze_dir),
        "silver": len(silver),
        "rejects": len(_rows(directory, "rejects")),
        "conflicts": len(_rows(directory, "conflicts")),
        "silver_unique_ids": len({r["event_id"] for r in silver}) == len(silver),
        "north_hour": north_hour
        and {
            "hour_start": north_hour["hour_start"].strftime("%Y-%m-%dT%H:%M:%SZ"),
            "readings": north_hour["readings"],
            "avg_pressure_bar": north_hour["avg_pressure_bar"],
        },
        "north_day_readings": sum(
            r["readings"] for r in daily if r["well_id"] == "NORTH-07"
        ),
        "pump_populated": sum(r["pump_current_a"] is not None for r in silver),
    }


def compare(observed: dict, expected: dict) -> list[str]:
    failures = []
    for key, want in expected.items():
        got = observed.get(key)
        ok = _close(got, want) if isinstance(want, dict) else got == want
        print(f"  {'OK  ' if ok else 'FAIL'} {key}: observed={got!r} expected={want!r}")
        if not ok:
            failures.append(key)
    if not observed["silver_unique_ids"]:
        print("  FAIL silver contains duplicate event_id")
        failures.append("silver_unique_ids")
    return failures


def _close(got: dict | None, want: dict) -> bool:
    if not got:
        return False
    return all(
        abs(got[k] - v) < 1e-9 if isinstance(v, float) else got[k] == v
        for k, v in want.items()
    )


def run(bronze_dir: Path, root: Path, stage: str) -> int:
    expected = EXPECTED[stage]
    observed = observe(bronze_dir, root)
    print(f"Verification stage: {stage}")
    failures = compare(observed, expected)
    print("RESULT:", "FAILED" if failures else "PASSED")
    return 1 if failures else 0
