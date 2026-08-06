"""The only module that talks to Discord's gateway."""

import logging
import sqlite3
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands, tasks

from creatorpulse import db
from creatorpulse.config import DiscordConfig, resolve_discord_config

logger = logging.getLogger("creatorpulse")

# A fixed offset rather than zoneinfo.ZoneInfo("Asia/Manila"): the Philippines has not observed
# daylight saving since 1978, so this offset is constant and needs no timezone database to
# confirm it. ZoneInfo would drag in the tzdata package on Windows (which ships no IANA
# database) purely to look up a fact that does not change — a dependency the no-new-dependencies
# rule does not justify. If a creator in a DST region is ever tracked, this becomes ZoneInfo and
# tzdata becomes a real dependency; until then it is arithmetic.
MANILA = timezone(timedelta(hours=8), "Asia/Manila")
# D-03's three-schedule ordering: 08:00 collector (systemd timer) -> 08:15 digest (this loop)
# -> 09:00 off-box watchdog (Apps Script trigger).
DIGEST_TIME = time(hour=8, minute=15, tzinfo=MANILA)
# Matches Phase 5 D-06's watchdog threshold exactly, defined once so the digest banner and
# the later /status command cannot disagree about what "stale" means.
STALE_AFTER_HOURS = 26

# REQUIREMENTS.md's BOT-02 says a delta that *exceeds* +-20% is flagged: a strict greater-than
# on the absolute value, so a pair sitting exactly on the threshold is not flagged. This reads
# percent_change's unrounded float, never format_percent's rounded string — a row displayed as
# +20.0% that is really +20.04% still carries the flag.
FLAG_THRESHOLD = 0.20
# The visible marker on a flagged row. Unflagged rows get an equal-width blank prefix instead
# of nothing, so the creator/source column stays aligned down the message in Discord's
# proportional font.
MOVER_FLAG = "🚨"
_UNFLAGGED_PREFIX = "  "

# D-16's "recent trend" length, applied per source in build_trend_text rather than as a SQL
# LIMIT — see CREATOR_TREND_SQL's comment in db.py for why a flat LIMIT would be wrong the
# moment a creator has two sources.
TREND_LIMIT = 7


def percent_change(views: int | None, prev_views: int | None) -> float | None:
    """(views - prev_views) / prev_views. None when either side is None or prev_views is 0 —
    a division by zero is not a gain, and a real 0 is not missing data (D-12, CLAUDE.md's
    NULL-vs-0 rule). Never rounded here; only the rendered text is rounded (format_percent),
    so display precision can never reorder a row or change a flag."""
    if views is None or prev_views is None or prev_views == 0:
        return None
    return (views - prev_views) / prev_views


def format_percent(pct: float) -> str:
    """One decimal place, explicit sign — display only."""
    return f"{pct * 100:+.1f}%"


def staleness_hours(finished_at: str, now: datetime) -> float:
    """Hours between a stored runs.finished_at and now. finished_at is a tz-aware UTC isoformat
    string written by collector.collect_once, so datetime.fromisoformat carries its offset and
    the subtraction needs no separate timezone handling."""
    finished = datetime.fromisoformat(finished_at)
    return (now - finished).total_seconds() / 3600


def build_digest_text(conn: sqlite3.Connection, now: datetime) -> str:
    """The staleness banner (D-04), every (creator, source) pair's latest snapshot sorted by
    |percent change| descending with pairs that have no computable percent sorted last
    (D-11/D-12) and flagged when that percent exceeds +-FLAG_THRESHOLD (D-10/BOT-02), and that
    run's failures (D-06). Pure and fixture-testable — it reaches only into db.py, so nothing
    in the digest path imports the gateway or the Google client."""
    header = f"CreatorPulse digest — {now.date().isoformat()}"
    lines = [header]

    last_run = db.fetch_last_run(conn)
    run_id: int | None = None
    if last_run is None:
        # No runs row at all — never a fabricated OK (PITFALLS.md §18(d)).
        lines.append("⚠ could not determine freshness — no runs recorded yet")
    else:
        run_id, _started_at, finished_at, _rows_written, _failure_count = last_run
        hours = staleness_hours(finished_at, now)
        # Strictly greater-than, matching Code.gs's checkFreshness: exactly STALE_AFTER_HOURS
        # reads fresh, so the two surfaces can never disagree about the same moment (D-17).
        if hours > STALE_AFTER_HOURS:
            lines.append(f"⚠ last run finished {finished_at} — STALE ({round(hours)}h ago)")

    rows = db.fetch_latest_rows(conn)
    if not rows:
        lines.append("No rows recorded yet.")
    else:
        computed = [
            (creator_id, source, views, prev_views, percent_change(views, prev_views))
            for creator_id, source, _followers, views, _collected_at, prev_views in rows
        ]

        def _sort_key(
            item: tuple[str, str, int | None, int | None, float | None],
        ) -> tuple[bool, float, str, str]:
            creator_id, source, _views, _prev_views, pct = item
            has_pct = pct is not None
            return (not has_pct, -abs(pct) if pct is not None else 0.0, creator_id, source)

        for creator_id, source, views, prev_views, pct in sorted(computed, key=_sort_key):
            views_text = f"{views:,}" if views is not None else db.DELTA_PLACEHOLDER
            if pct is None:
                # No baseline, or a zero baseline, is never flagged (D-12).
                delta_text = db.DELTA_PLACEHOLDER
                flagged = False
            else:
                # pct is not None only when both sides are ints and prev_views != 0.
                assert views is not None and prev_views is not None
                delta_text = f"{views - prev_views:+,}, {format_percent(pct)}"
                flagged = abs(pct) > FLAG_THRESHOLD
            prefix = f"{MOVER_FLAG} " if flagged else _UNFLAGGED_PREFIX
            lines.append(f"{prefix}{creator_id} / {source} — {views_text} views (Δ {delta_text})")

    if run_id is not None:
        # No runs row at all means no run whose failures could be listed — the
        # could-not-determine banner above already carries that fact, so the section is
        # omitted entirely rather than rendered empty (D-06).
        failures = db.fetch_run_failures(conn, run_id)
        if failures:
            lines.append(f"Failures this run: {len(failures)}")
            for creator_id, source, cause, message in failures:
                lines.append(f"   {creator_id} / {source} — {cause}: {message}")
        else:
            # An absent section would be indistinguishable from a section that failed to
            # render — a clean run says so explicitly.
            lines.append("Failures this run: none")

    return "\n".join(lines)


def build_trend_text(conn: sqlite3.Connection, name: str) -> str:
    """/creator's formatter (D-15/D-16). Matches name against fetch_known_creators()'s
    output case-insensitively and exactly.

    str.lower() rather than str.casefold(): config._SLUG_RE already constrains every
    creator_id to lowercase ASCII letters, digits, and hyphens, so a plain lower() is an
    exact inverse over that alphabet, while a non-ASCII lookalike (a dotted capital I, for
    example) folds to a string no id can ever equal and falls through to the unknown-name
    reply below rather than matching something unexpected. No substring matching, no fuzzy
    matching — there is no ambiguity rule to defend for a handful of creators with distinct
    names, and no path by which the bot quietly answers about the wrong one (D-15).
    """
    known = db.fetch_known_creators(conn)
    normalized = name.strip().lower()

    if normalized not in known:
        if not known:
            return "The database has no creators recorded yet."
        return f"No creator named {name!r} — known creators: {', '.join(known)}"

    rows = db.fetch_creator_trend(conn, normalized)
    by_source: dict[str, list[tuple[str, int | None]]] = {}
    for source, metric_date, views in rows:
        # Rows already arrive newest-first per source (CREATOR_TREND_SQL's ORDER BY) — no
        # re-sort needed here.
        by_source.setdefault(source, []).append((metric_date, views))

    lines = [f"Recent trend for {normalized}:"]
    for source in sorted(by_source):
        window = by_source[source][:TREND_LIMIT]
        lines.append(f"{normalized} / {source}")
        for i, (metric_date, views) in enumerate(window):
            # Views render blank on NULL, the number on 0 — build_dashboard_rows's rule,
            # not the digest's em-dash-for-views rule (CLAUDE.md's NULL-vs-0 discipline).
            views_text = "" if views is None else f"{views:,}"
            # The delta is against the next-older row *within this window*: the oldest
            # line shown always carries the em dash, even when older rows exist beyond the
            # seven-row cut, and NULL on either side never computes a delta against a
            # missing number (D-12).
            older_views = window[i + 1][1] if i + 1 < len(window) else None
            if views is None or older_views is None:
                delta_text = db.DELTA_PLACEHOLDER
            else:
                delta_text = f"{views - older_views:+,}"
            lines.append(f"  {metric_date}: {views_text} views (Δ {delta_text})")

    return "\n".join(lines)


def build_status_text(conn: sqlite3.Connection, now: datetime) -> str:
    """/status's formatter (D-17). Reuses fetch_last_run(), staleness_hours(), and
    STALE_AFTER_HOURS exactly as build_digest_text's banner does, so the digest and /status
    can never disagree about whether the system is stale."""
    last_run = db.fetch_last_run(conn)
    if last_run is None:
        # Never a fabricated OK from an empty database (PITFALLS.md §18(d)); Phase 7
        # criterion 2 grades this command on reporting staleness honestly.
        return "No run has been recorded yet."

    run_id, started_at, finished_at, rows_written, failure_count = last_run
    duration_seconds = (
        datetime.fromisoformat(finished_at) - datetime.fromisoformat(started_at)
    ).total_seconds()
    # Strictly greater-than, the same constant and the same comparison direction as the
    # digest banner and Phase 5's watchdog — exactly STALE_AFTER_HOURS reads OK everywhere.
    hours = staleness_hours(finished_at, now)
    verdict = "STALE" if hours > STALE_AFTER_HOURS else "OK"

    lines = [
        f"Last run finished {finished_at} — {verdict}",
        f"Duration: {duration_seconds:.1f}s",
        f"Rows written: {rows_written}",
        f"Failures: {failure_count}",
    ]
    if failure_count > 0:
        # The same rows the digest lists and the collector's own alert was built from, so
        # all three surfaces name the same failures for the same run.
        for creator_id, source, cause, message in db.fetch_run_failures(conn, run_id):
            lines.append(f"  {creator_id} / {source} — {cause}: {message}")

    return "\n".join(lines)


class CreatorPulseBot(commands.Bot):
    """Long-lived gateway client: guild-scoped slash commands, a guarded digest task loop, and
    nothing else. No module-level database connection anywhere in this file — every read
    opens, queries, and closes its own connection (ROADMAP's pre-locked note)."""

    def __init__(self, config: DiscordConfig, db_path: Path, *, digest_now: bool) -> None:
        # command_prefix is required by the constructor and unused — this bot is slash-only.
        # Intents.default() and nothing else: slash commands arrive as interactions, not
        # messages, so message_content (a privileged intent) is never requested (criterion
        # 5's whole answer, and threat T-06-05).
        super().__init__(command_prefix="!", intents=discord.Intents.default())
        self.config = config
        self.db_path = db_path
        self.digest_now = digest_now
        self.channel: discord.abc.Messageable | None = None
        self._register_commands()

    def _register_commands(self) -> None:
        """Both slash commands, registered once at construction so setup_hook's guild sync
        has something to sync. Each handler opens a short-lived read connection, calls one
        pure formatter, and closes it in a finally — no module-level connection anywhere in
        this file (ROADMAP's pre-locked note). Neither defers: a single indexed SQLite read
        finishes comfortably inside Discord's 3-second initial-response window
        (06-RESEARCH Priority 4), so deferring would add a second round trip for nothing."""

        @self.tree.command(
            name="creator", description="Show a creator's last seven recorded days, per source"
        )
        @app_commands.describe(name="creator id, case-insensitive (e.g. kaicenat)")
        async def creator_command(interaction: discord.Interaction, name: str) -> None:
            conn = db.connect(self.db_path, create=False)
            try:
                text = build_trend_text(conn, name)
            finally:
                conn.close()
            await interaction.response.send_message(
                text, allowed_mentions=discord.AllowedMentions.none()
            )

        @self.tree.command(name="status", description="Report the last collector run's status")
        async def status_command(interaction: discord.Interaction) -> None:
            # DatabaseNotInitialized is allowed to propagate rather than being turned into a
            # friendly reply — a bot answering "everything's fine" while pointed at a
            # database that does not exist is the failure mode this project has refused at
            # every prior boundary.
            conn = db.connect(self.db_path, create=False)
            try:
                text = build_status_text(conn, datetime.now(MANILA))
            finally:
                conn.close()
            await interaction.response.send_message(
                text, allowed_mentions=discord.AllowedMentions.none()
            )

    async def setup_hook(self) -> None:
        guild = discord.Object(id=self.config.guild_id)
        # Guild-scoped, not global: propagates immediately rather than taking up to an hour.
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)

        # Channel preflight (06-RESEARCH Pitfall 2): an integer that parses fine can still
        # name a channel this bot cannot see or post in. Fail loudly here, before the digest
        # loop ever starts, rather than letting the first channel.send() at 08:15 be the
        # first time this surfaces.
        resolved = self.get_channel(self.config.channel_id)
        if resolved is None:
            try:
                resolved = await self.fetch_channel(self.config.channel_id)
            except (discord.NotFound, discord.Forbidden) as exc:
                raise RuntimeError(
                    f"channel {self.config.channel_id} not visible or not postable by this "
                    "bot — check the invite's channel permissions"
                ) from exc
        if not isinstance(resolved, discord.abc.Messageable):
            raise RuntimeError(
                f"channel {self.config.channel_id} is not a postable channel type — check "
                "DISCORD_CHANNEL_ID"
            )
        self.channel = resolved
        logger.info("resolved digest channel id=%s", self.config.channel_id)

        if self.digest_now:
            await self.post_digest()
        self.digest_loop.start()

    async def post_digest(self) -> None:
        assert self.channel is not None  # setup_hook always resolves this before use
        conn = db.connect(self.db_path, create=False)
        try:
            text = build_digest_text(conn, datetime.now(MANILA))
        finally:
            conn.close()
        await self.channel.send(text, allowed_mentions=discord.AllowedMentions.none())

    @tasks.loop(time=DIGEST_TIME)
    async def digest_loop(self) -> None:
        # The one place in this codebase that catches bare Exception, and the divergence is
        # deliberate: tasks.loop's reconnect=True machinery only retries OSError,
        # GatewayNotFound, ConnectionClosed, aiohttp.ClientError, and asyncio.TimeoutError
        # (06-RESEARCH Pitfall 1, verified against the pinned v2.7.1 source). Any other
        # exception here would kill this loop's underlying Task permanently after one log
        # line, while systemd keeps reporting the unit healthy — the digest would simply
        # never fire again with no other symptom.
        try:
            await self.post_digest()
        except Exception:
            logger.exception("digest tick failed; next scheduled time will retry")

    @digest_loop.before_loop
    async def _before_digest(self) -> None:
        await self.wait_until_ready()  # channel objects do not resolve before READY


def run_bot(db_path: Path, *, digest_now: bool) -> int:
    """Resolve config, connect, run. resolve_discord_config() runs first so a config problem
    stops the process before anything connects (D-19). An invalid token surfaces as
    discord.LoginFailure with a non-zero exit — deliberately not caught here, so systemd
    marks the unit failed and the journal names the cause (06-RESEARCH Pitfall 3)."""
    config = resolve_discord_config()
    client = CreatorPulseBot(config, db_path, digest_now=digest_now)
    client.run(config.bot_token, log_handler=None)
    return 0
