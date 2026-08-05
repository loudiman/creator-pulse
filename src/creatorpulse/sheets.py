"""The only module that talks to Google. Reads metrics via db.py, writes the Dashboard tab."""

import json
import logging
import sqlite3
from collections.abc import Sequence
from pathlib import Path

import gspread
from gspread.utils import ValueInputOption

logger = logging.getLogger("creatorpulse")

DASHBOARD_TAB = "Dashboard"
DELTA_PLACEHOLDER = "—"  # em dash; 04-02 puts a real number beside it


class SheetNotShared(Exception):
    """Raised when the Sheet is not shared with the service account, or shared as Viewer
    rather than Editor (D-08, SHEET-07)."""


class SheetsKeyfileUnusable(Exception):
    """Raised when CREATORPULSE_SHEETS_KEYFILE is missing, unreadable, or not valid JSON —
    checked before any network call (D-08, SHEET-07)."""

# Exactly six entries, columns A..F. Length is what keeps the write range from reaching G —
# the range is built from len(values) and the literal letter F, so a header edit here cannot
# silently push a value into the human-owned Status column. SHEET-02's "labelled coarse"
# obligation is discharged once here, in the header, not per cell — a per-cell annotation
# would make the column non-numeric and break the formatting Phase 5 keys on.
HEADERS: list[str] = [
    "Creator",
    "Source",
    "Followers (coarse)",
    "Views",
    "Δ Views",
    "Last updated (UTC)",
]

# Correlated on (creator_id, metric_date), so this uses idx_metrics_creator_date. Rejected
# alternatives: SQLite's bare-column-with-MAX() shorthand is a SQLite quirk rather than
# standard SQL (the merge rule: nothing enters the repo the author cannot explain out loud);
# a separate DISTINCT-pairs query plus a per-pair lookup would be N+1 queries for the same
# answer. This one query yields the DISTINCT (creator_id, source) pairs D-01 names, plus each
# pair's latest snapshot, in one pass.
LATEST_ROWS_SQL = """
SELECT m.creator_id, m.source, m.followers, m.views, m.collected_at, prev.views
FROM metrics AS m
LEFT JOIN metrics AS prev
    -- keyed on (creator_id, metric_date): idx_metrics_creator_date's exact column pair
    ON prev.creator_id = m.creator_id
    AND prev.source = m.source
    AND prev.metric_date = date(m.metric_date, '-1 day')
WHERE m.metric_date = (
    SELECT MAX(m2.metric_date) FROM metrics AS m2
    WHERE m2.creator_id = m.creator_id AND m2.source = m.source
)
ORDER BY m.creator_id, m.source;
"""

LatestRow = tuple[str, str, int | None, int | None, str, int | None]


def fetch_latest_rows(conn: sqlite3.Connection) -> list[LatestRow]:
    """One indexed read of metrics: each (creator_id, source) pair's latest snapshot."""
    cursor = conn.execute(LATEST_ROWS_SQL)
    rows: list[LatestRow] = cursor.fetchall()
    return rows


def build_dashboard_rows(rows: Sequence[LatestRow]) -> list[list[object]]:
    """The pure, fixture-testable core. Header row first (a copy, never the module constant
    itself, so a caller mutating the result cannot corrupt HEADERS), then one row per pair.

    The NULL rule here is load-bearing and a correctness rule, not a style preference: None
    means "this platform does not expose this metric" and renders as an empty cell; 0 means
    "the platform reported zero" and renders as the number zero. They must never merge.
    """
    values: list[list[object]] = [list(HEADERS)]
    for creator_id, source, followers, views, collected_at, prev_views in rows:
        values.append(
            [
                creator_id,
                source,
                "" if followers is None else followers,
                "" if views is None else views,
                DELTA_PLACEHOLDER if views is None or prev_views is None else views - prev_views,
                collected_at,
            ]
        )
    return values


def _client_email_from_keyfile(keyfile: Path) -> str | None:
    """Read exactly the client_email field out of the service-account JSON — a public
    address, safe to name in an exception message. Returns None on OSError, on malformed
    JSON, and when the parsed payload is not a mapping. Never reaches for any other field and
    never returns or logs the file's contents — private_key and friends are credential
    material (T-04-10)."""
    try:
        payload = json.loads(keyfile.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    email = payload.get("client_email")
    return email if isinstance(email, str) else None


def _open_worksheet(sheet_id: str, keyfile: Path) -> gspread.Worksheet:
    """Narrowed to the spreadsheets scope alone — open_by_key needs only the Sheets API, so a
    leaked key reaches Sheets and nothing else in Drive.

    Two separate try blocks, deliberately not merged (D-08's CORRECTION): PermissionError is
    an OSError subclass, so a single combined try would report an unshared Sheet as a
    key-file problem — the exact misdiagnosis SHEET-07 exists to prevent.
    """
    try:
        client = gspread.service_account(
            filename=keyfile, scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise SheetsKeyfileUnusable(
            f"service-account key file {keyfile} is missing or not valid JSON — check "
            f"CREATORPULSE_SHEETS_KEYFILE ({exc})"
        ) from exc

    try:
        spreadsheet = client.open_by_key(sheet_id)
    except PermissionError as exc:
        # The verified primary case (D-08 CORRECTION): a bare builtin with no message.
        email = _client_email_from_keyfile(keyfile)
        if email is None:
            raise SheetNotShared(
                f"Sheet {sheet_id} is not shared with the service account, and its address "
                f"could not be read from key file {keyfile} — check the file, then share the "
                "Sheet with the address in its client_email field as Editor"
            ) from exc
        raise SheetNotShared(
            f"Sheet {sheet_id} is not shared with the service account {email} — share it "
            "with that address as Editor"
        ) from exc
    except gspread.exceptions.SpreadsheetNotFound as exc:
        raise SheetNotShared(
            f"spreadsheet id {sheet_id!r} was not found — check CREATORPULSE_SHEET_ID (a "
            "deleted Sheet reads the same way)"
        ) from exc
    except gspread.exceptions.APIError as exc:
        if exc.response.status_code == 403:
            email = _client_email_from_keyfile(keyfile)
            addressee = email if email is not None else "the address in the key file"
            raise SheetNotShared(
                f"Sheet {sheet_id} refused access for {addressee} — share it as Editor"
            ) from exc
        raise  # a 500 or 429 is a transient API failure, not a permission problem

    return spreadsheet.worksheet(DASHBOARD_TAB)


def sync(conn: sqlite3.Connection, sheet_id: str, keyfile: Path) -> int:
    """Read metrics, build the array, write it in one call. Returns the DATA row count.

    The only write in this module — no loop, no second call, no per-cell method (SHEET-05).
    The range's last column letter is a literal F, never computed from a column count, so
    column G cannot drift into it (SHEET-06). USER_ENTERED is what makes columns C, D, and F
    land as real numbers and a real timestamp (PITFALLS.md §5). The header row is inside
    values on every run, so a hand-edited header self-heals. The tab is never cleared,
    resized, or row-deleted (PITFALLS.md §6).
    """
    values = build_dashboard_rows(fetch_latest_rows(conn))
    range_name = f"A1:F{len(values)}"
    worksheet = _open_worksheet(sheet_id, keyfile)
    try:
        worksheet.update(values, range_name, value_input_option=ValueInputOption.user_entered)
    except gspread.exceptions.APIError as exc:
        if exc.response.status_code == 403:
            # The Viewer-not-Editor case: open_by_key succeeded (reading is exactly what
            # Viewer permits), so a preflight on the open alone cannot see this.
            raise SheetNotShared(
                f"Sheet {sheet_id} opened for reading but the write was refused — the share "
                "is Viewer, and it needs to be Editor"
            ) from exc
        raise  # a 500 or 429 is a transient API failure, not a permission problem
    data_row_count = len(values) - 1
    logger.info("Wrote %d data rows to %s", data_row_count, range_name)
    return data_row_count
