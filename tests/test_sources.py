"""Tests for creatorpulse.sources._retry and the YouTube fixture-in / record-out cases.

Fixtures only, no live network calls. The retry cases drive a scripted local callable against a
faked clock (`time.sleep` monkeypatched) — no HTTP server, no real waiting. This file is created
here and extended by `03-03` with the Twitch cases once SRC-02 unblocks; not created twice.
"""

import json
from datetime import date
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

from creatorpulse.sources import youtube
from creatorpulse.sources._retry import retry

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _response(status_code: int) -> Mock:
    resp = Mock(spec=requests.Response)
    resp.status_code = status_code
    return resp


def _youtube_response(fixture_name: str) -> Mock:
    body = json.loads((FIXTURES / "youtube" / fixture_name).read_text(encoding="utf-8"))
    resp = Mock(spec=requests.Response)
    resp.status_code = 200
    resp.json.return_value = body
    resp.raise_for_status.return_value = None
    return resp


class _ScriptedCall:
    """Returns or raises the next scripted outcome on each call — no HTTP server involved."""

    def __init__(self, outcomes: list[BaseException | Mock]) -> None:
        self._outcomes = outcomes
        self.calls = 0

    def __call__(self, *args: object, **kwargs: object) -> Mock:
        outcome = self._outcomes[self.calls]
        self.calls += 1
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def test_retries_on_timeout_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("creatorpulse.sources._retry.time.sleep", sleeps.append)
    fn = _ScriptedCall([requests.Timeout(), requests.Timeout(), _response(200)])

    wrapped = retry(fn, creator_id="xqc", source="youtube")
    result = wrapped()

    assert result.status_code == 200
    assert sleeps == [2.0, 4.0]


def test_retries_on_connection_error_all_three_reraises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("creatorpulse.sources._retry.time.sleep", sleeps.append)
    error = requests.ConnectionError()
    fn = _ScriptedCall([error, error, error])

    wrapped = retry(fn, creator_id="xqc", source="youtube")
    with pytest.raises(requests.ConnectionError):
        wrapped()

    assert sleeps == [2.0, 4.0]  # never a third sleep after the last attempt


def test_retries_on_429_then_succeeds(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("creatorpulse.sources._retry.time.sleep", sleeps.append)
    fn = _ScriptedCall([_response(429), _response(200)])

    with caplog.at_level("INFO", logger="creatorpulse"):
        wrapped = retry(fn, creator_id="xqc", source="youtube")
        result = wrapped()

    assert result.status_code == 200
    assert sleeps == [2.0]
    retry_lines = [r.getMessage() for r in caplog.records if "retry" in r.getMessage()]
    assert len(retry_lines) == 1
    assert "creator=xqc" in retry_lines[0]
    assert "source=youtube" in retry_lines[0]
    assert "attempt=1" in retry_lines[0]


def test_503_all_three_attempts_returned_as_is(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("creatorpulse.sources._retry.time.sleep", sleeps.append)
    fn = _ScriptedCall([_response(503), _response(503), _response(503)])

    wrapped = retry(fn, creator_id="xqc", source="youtube")
    result = wrapped()

    # returned, not raised — the caller's raise_for_status() is what surfaces it
    assert result.status_code == 503
    assert sleeps == [2.0, 4.0]


def test_403_returns_immediately_no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("creatorpulse.sources._retry.time.sleep", sleeps.append)
    fn = _ScriptedCall([_response(403)])  # YouTube's quotaExceeded shape (D-14)

    wrapped = retry(fn, creator_id="xqc", source="youtube")
    result = wrapped()

    assert result.status_code == 403
    assert sleeps == []


@pytest.mark.parametrize("status_code", [401, 404])
def test_non_retryable_status_returns_immediately_no_sleep(
    monkeypatch: pytest.MonkeyPatch, status_code: int
) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("creatorpulse.sources._retry.time.sleep", sleeps.append)
    fn = _ScriptedCall([_response(status_code)])

    wrapped = retry(fn, creator_id="xqc", source="youtube")
    result = wrapped()

    assert result.status_code == status_code
    assert sleeps == []


def test_youtube_ok_channel_returns_integer_followers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YOUTUBE_API_KEY", "fake-key-for-test")
    resp = _youtube_response("channel_ok.json")
    monkeypatch.setattr("creatorpulse.sources.youtube.requests.get", lambda *a, **kw: resp)

    record = youtube.fetch("@xQcOW", date(2026, 8, 4))

    assert isinstance(record.followers, int)  # a real, disclosed subscriber count


def test_youtube_hidden_subscriber_count_maps_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YOUTUBE_API_KEY", "fake-key-for-test")
    resp = _youtube_response("channel_hidden_subs_derived.json")
    monkeypatch.setattr("creatorpulse.sources.youtube.requests.get", lambda *a, **kw: resp)

    record = youtube.fetch("@somehandle", date(2026, 8, 4))

    assert record.followers is None  # D-03 rule 1 — never 0, even though flag+"0" is present


def test_youtube_hidden_subscriber_count_omitted_key_maps_to_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("YOUTUBE_API_KEY", "fake-key-for-test")
    resp = _youtube_response("channel_hidden_subs_omitted_derived.json")
    monkeypatch.setattr("creatorpulse.sources.youtube.requests.get", lambda *a, **kw: resp)

    record = youtube.fetch("@somehandle", date(2026, 8, 4))

    assert record.followers is None  # proves subscriberCount is never read on the hidden path
