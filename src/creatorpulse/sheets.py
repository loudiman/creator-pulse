"""The only module that talks to Google. Reads metrics via db.py, writes the Dashboard tab."""

import logging
import sqlite3
from collections.abc import Sequence
from pathlib import Path

import gspread
from gspread.utils import ValueInputOption

logger = logging.getLogger("creatorpulse")

DASHBOARD_TAB = "Dashboard"
DELTA_PLACEHOLDER = "—"  # em dash; 04-02 puts a real number beside it

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
SELECT m.creator_id, m.source, m.followers, m.views, m.collected_at
FROM metrics AS m
WHERE m.metric_date = (
    SELECT MAX(m2.metric_date) FROM metrics AS m2
    WHERE m2.creator_id = m.creator_id AND m2.source = m.source
)
ORDER BY m.creator_id, m.source;
"""

LatestRow = tuple[str, str, int | None, int | None, str]


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
    for creator_id, source, followers, views, collected_at in rows:
        values.append(
            [
                creator_id,
                source,
                "" if followers is None else followers,
                "" if views is None else views,
                DELTA_PLACEHOLDER,
                collected_at,
            ]
        )
    return values


def _open_worksheet(sheet_id: str, keyfile: Path) -> gspread.Worksheet:
    """Narrowed to the spreadsheets scope alone — open_by_key needs only the Sheets API, so a
    leaked key reaches Sheets and nothing else in Drive. Catches nothing: SheetNotShared and
    the client_email message are 04-03's SHEET-07 work; WorksheetNotFound already names the
    tab title it looked for."""
    client = gspread.service_account(
        filename=keyfile, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    spreadsheet = client.open_by_key(sheet_id)
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
    worksheet.update(values, range_name, value_input_option=ValueInputOption.user_entered)
    data_row_count = len(values) - 1
    logger.info("Wrote %d data rows to %s", data_row_count, range_name)
    return data_row_count
