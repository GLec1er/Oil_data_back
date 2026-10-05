from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class Granularity(str, Enum):
    hourly = "hourly"
    daily = "daily"


class MartRow(BaseModel):
    period_start: datetime
    well_id: str
    readings: int
    avg_pressure_bar: float
    avg_temperature_c: float
    avg_flow_m3_h: float
    max_water_cut_pct: float


class SnapshotInfo(BaseModel):
    snapshot_id: str
    published_at: datetime
    counts: dict[str, int]


class MartPage(BaseModel):
    snapshot_id: str
    published_at: datetime
    total: int
    limit: int
    offset: int
    items: list[MartRow]


class WellList(BaseModel):
    snapshot_id: str
    wells: list[str]
