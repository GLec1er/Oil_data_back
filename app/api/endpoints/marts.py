from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.config import settings
from app.schemas.marts import Granularity, MartPage, SnapshotInfo, WellList
from app.services import marts

router = APIRouter(tags=["marts"])


def get_marts_dir() -> Path:
    return settings.marts_dir


def _unavailable(error: marts.SnapshotUnavailable) -> HTTPException:
    return HTTPException(status_code=503, detail=str(error), headers={"Retry-After": "15"})


# Plain `def` endpoints run in FastAPI's threadpool, so blocking Parquet reads
# never stall the event loop.
@router.get("/snapshot", response_model=SnapshotInfo)
def snapshot(marts_dir: Path = Depends(get_marts_dir)):
    try:
        manifest, _ = marts.read_table(marts_dir, "daily")
    except marts.SnapshotUnavailable as error:
        raise _unavailable(error) from error
    return manifest


@router.get("/wells", response_model=WellList)
def wells(marts_dir: Path = Depends(get_marts_dir)):
    try:
        manifest, names = marts.list_wells(marts_dir)
    except marts.SnapshotUnavailable as error:
        raise _unavailable(error) from error
    return {"snapshot_id": manifest["snapshot_id"], "wells": names}


@router.get("/marts/{granularity}", response_model=MartPage)
def mart(
    granularity: Granularity,
    well_id: str | None = None,
    start: datetime | None = Query(None, description="Inclusive period start (UTC if naive)"),
    end: datetime | None = Query(None, description="Exclusive period end (UTC if naive)"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    marts_dir: Path = Depends(get_marts_dir),
):
    if start and end and start >= end:
        raise HTTPException(status_code=422, detail="start must be before end")
    try:
        manifest, total, rows = marts.query_mart(
            marts_dir,
            granularity.value,
            well_id=well_id,
            start=start,
            end=end,
            limit=limit,
            offset=offset,
        )
    except marts.SnapshotUnavailable as error:
        raise _unavailable(error) from error
    return {
        "snapshot_id": manifest["snapshot_id"],
        "published_at": manifest["published_at"],
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": rows,
    }
