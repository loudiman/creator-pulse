"""Retry wrapper for source HTTP calls — narrow list, fixed backoff, source layer only (D-13/D-14).

Lives here and nowhere else: the orchestrator (`collector.py`) must stay ignorant of HTTP status
codes and `requests` exception types (ARCHITECTURE.md Anti-Pattern 1). Imports nothing from
`creatorpulse.sources`' own `__init__`, so a sibling source module can import this submodule
directly while the package is still initialising.
"""

import logging
import time
from collections.abc import Callable

import requests

logger = logging.getLogger("creatorpulse")

_RETRYABLE_EXC = (requests.Timeout, requests.ConnectionError)
_RETRYABLE_STATUS = {429}


def _is_retryable_status(status_code: int) -> bool:
    return status_code in _RETRYABLE_STATUS or status_code >= 500


def retry[**P](
    fn: Callable[P, requests.Response],
    *,
    creator_id: str,
    source: str,
    max_attempts: int = 3,
) -> Callable[P, requests.Response]:
    """Wrap `fn` (a `requests.get`-shaped call) with three attempts, 2s-then-4s fixed backoff.

    `creator_id` is the `creators.yaml` identifier this call is for, used only in the retry log
    line — it also accepts the sentinel `"_token"` for a call that happens before any
    creator-specific work (the deferred `03-03` Twitch token mint is its only future consumer;
    nothing passes it yet, and it is a documented forward reference, not dead code).
    """

    def wrapped(*args: P.args, **kwargs: P.kwargs) -> requests.Response:
        for attempt in range(1, max_attempts + 1):
            try:
                response = fn(*args, **kwargs)
                if response.status_code < 400 or not _is_retryable_status(response.status_code):
                    return response  # success OR a non-retryable error (401/403/404/...)
                if attempt == max_attempts:
                    return response  # let the caller's .raise_for_status() surface it
            except _RETRYABLE_EXC:
                if attempt == max_attempts:
                    raise
            logger.info("retry creator=%s source=%s attempt=%d", creator_id, source, attempt)
            time.sleep(2.0 * attempt)  # 2s, then 4s — the same every time (D-14)
        raise AssertionError("unreachable")  # loop always returns or raises above

    return wrapped
