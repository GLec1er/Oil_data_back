import shutil

import pytest
from fastapi.testclient import TestClient

from app.api.endpoints.marts import get_marts_dir
from app.main import app
from app.services import marts
from pipeline import scenario
from pipeline.snapshot import materialize
from tests.pipeline_helpers import write_bronze


@pytest.fixture
def marts_dir(tmp_path):
    bronze = tmp_path / "bronze"
    root = tmp_path / "marts"
    offset = write_bronze(bronze, scenario.baseline(), 0, "b1.parquet")
    write_bronze(bronze, scenario.outage(), offset, "b2.parquet")
    materialize(bronze, root, "materializer-0000000001")
    return root


@pytest.fixture
def client(marts_dir):
    app.dependency_overrides[get_marts_dir] = lambda: marts_dir
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def empty_client(tmp_path):
    app.dependency_overrides[get_marts_dir] = lambda: tmp_path / "nothing"
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_snapshot_reports_active_manifest(client):
    body = client.get("/api/v1/snapshot").json()
    assert body["snapshot_id"] == "materializer-0000000001"
    assert body["counts"]["silver"] == 5


def test_wells_are_listed_sorted(client):
    assert client.get("/api/v1/wells").json()["wells"] == ["EAST-12", "NORTH-07"]


def test_hourly_matches_the_scenario_result(client):
    body = client.get("/api/v1/marts/hourly", params={"well_id": "NORTH-07"}).json()
    assert body["total"] == 2
    first = body["items"][0]
    assert first["period_start"].startswith("2026-10-01T10:00:00")
    assert first["readings"] == 3
    assert first["avg_pressure_bar"] == pytest.approx(100.0)


def test_daily_counts_all_readings_of_a_well(client):
    body = client.get("/api/v1/marts/daily", params={"well_id": "NORTH-07"}).json()
    assert [row["readings"] for row in body["items"]] == [4]


def test_time_range_is_inclusive_start_exclusive_end(client):
    params = {"well_id": "NORTH-07", "start": "2026-10-01T10:00:00Z", "end": "2026-10-01T11:00:00Z"}
    body = client.get("/api/v1/marts/hourly", params=params).json()
    assert [row["readings"] for row in body["items"]] == [3]


def test_naive_timestamps_are_treated_as_utc(client):
    params = {"start": "2026-10-01T11:00:00"}
    body = client.get("/api/v1/marts/hourly", params=params).json()
    assert body["total"] == 1


def test_pagination_reports_total_and_slices(client):
    body = client.get("/api/v1/marts/hourly", params={"limit": 1, "offset": 1}).json()
    assert body["total"] == 3
    assert len(body["items"]) == 1
    assert body["limit"] == 1 and body["offset"] == 1


def test_unknown_well_returns_empty_page(client):
    body = client.get("/api/v1/marts/hourly", params={"well_id": "NOPE"}).json()
    assert body["total"] == 0 and body["items"] == []


@pytest.mark.parametrize(
    "path, params",
    [
        ("/api/v1/marts/weekly", {}),
        ("/api/v1/marts/hourly", {"limit": 0}),
        ("/api/v1/marts/hourly", {"limit": 5000}),
        ("/api/v1/marts/hourly", {"offset": -1}),
        ("/api/v1/marts/hourly", {"start": "not-a-date"}),
        ("/api/v1/marts/hourly", {"start": "2026-10-02T00:00:00Z", "end": "2026-10-01T00:00:00Z"}),
    ],
)
def test_invalid_requests_are_rejected(client, path, params):
    assert client.get(path, params=params).status_code == 422


@pytest.mark.parametrize("path", ["/api/v1/snapshot", "/api/v1/wells", "/api/v1/marts/hourly"])
def test_503_with_retry_hint_before_first_snapshot(empty_client, path):
    response = empty_client.get(path)
    assert response.status_code == 503
    assert response.headers["retry-after"] == "15"


def test_read_retries_when_snapshot_is_pruned_midway(marts_dir, monkeypatch):
    real = marts._read_once
    calls = []

    def flaky(root, name):
        calls.append(name)
        if len(calls) == 1:
            raise FileNotFoundError("pruned")
        return real(root, name)

    monkeypatch.setattr(marts, "_read_once", flaky)
    manifest, table = marts.read_table(marts_dir, "hourly")
    assert len(calls) == 2 and table.num_rows == 3


def test_persistently_missing_files_become_unavailable(marts_dir):
    shutil.rmtree(marts_dir / "snapshots")
    with pytest.raises(marts.SnapshotUnavailable):
        marts.read_table(marts_dir, "hourly")


def test_cors_allows_the_static_site_origin(client):
    origin = "http://localhost:8080"
    response = client.get("/api/v1/wells", headers={"Origin": origin})
    assert response.headers["access-control-allow-origin"] == origin


def test_cors_does_not_allow_unknown_origins(client):
    response = client.get("/api/v1/wells", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in response.headers


def test_cors_rejects_non_get_preflight(client):
    response = client.options(
        "/api/v1/wells",
        headers={"Origin": "http://localhost:8080", "Access-Control-Request-Method": "DELETE"},
    )
    assert response.status_code == 400
