"""YouTube Data API v3 channel-statistics fetch and the normalization boundary."""

import os
from datetime import UTC, date, datetime
from typing import Any

import requests

from creatorpulse.models import MetricRecord

_BASE_URL = "https://www.googleapis.com/youtube/v3/channels"


class ChannelNotFound(Exception):
    """Raised when forHandle matches zero channels (D-18) — HTTP 200 with no usable items."""


def fetch(identifier: str, metric_date: date) -> MetricRecord:
    api_key = os.environ["YOUTUBE_API_KEY"]
    params = {"part": "statistics", "forHandle": identifier, "key": api_key}
    response = requests.get(_BASE_URL, params=params, timeout=10)
    response.raise_for_status()
    body: dict[str, Any] = response.json()

    # D-18: a bogus handle returns HTTP 200. The recorded channel_not_found.json fixture
    # shows the `items` key absent entirely (not an empty list) — data.get(...), never
    # data[...], so this is a named ChannelNotFound rather than a bare KeyError.
    items = body.get("items")
    if not items:
        raise ChannelNotFound(f"forHandle={identifier!r} matched zero channels")

    stats = items[0]["statistics"]
    # Branch on the flag, never on the value: read hiddenSubscriberCount FIRST so the
    # subscriberCount key is never touched on the hidden path (D-03 rule 1).
    hidden = stats["hiddenSubscriberCount"]
    followers = None if hidden else int(stats["subscriberCount"])

    return MetricRecord(
        creator_id="",  # filled in by collector.py — this module stays DB-agnostic
        source="youtube",
        metric_date=metric_date,
        followers=followers,
        views=int(stats["viewCount"]),
        likes=None,
        video_count=int(stats["videoCount"]),
        is_live=None,
        collected_at=datetime.now(UTC),
    )
