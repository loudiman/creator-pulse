"""Fetcher registry and the source-adapter contract — a Protocol plus a plain dict, no ABC."""

from datetime import date
from typing import Protocol

from creatorpulse.models import MetricRecord

KNOWN_PLATFORMS = frozenset({"youtube", "twitch", "tiktok"})  # D-09 list 1


class SourceFetcher(Protocol):
    def __call__(self, identifier: str, metric_date: date) -> MetricRecord: ...


from creatorpulse.sources import youtube  # noqa: E402

FETCHERS: dict[str, SourceFetcher] = {  # D-09 list 2 — only implemented sources
    "youtube": youtube.fetch,
}
