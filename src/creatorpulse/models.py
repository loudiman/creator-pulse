"""Normalized metric record and per-run result — the shared shape both processes import."""

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class MetricRecord:
    creator_id: str
    source: str
    metric_date: date
    followers: int | None
    views: int | None
    likes: int | None
    video_count: int | None
    is_live: int | None
    collected_at: datetime


@dataclass(frozen=True, slots=True)
class RunFailure:
    creator_id: str
    source: str
    cause: str
    message: str


@dataclass(frozen=True, slots=True)
class RunResult:
    rows_written: int
    failure_count: int
    failures: tuple[RunFailure, ...]
