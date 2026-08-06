"""The only module that talks to Discord's gateway."""

import logging
import sqlite3
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

import discord
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


def build_digest_text(conn: sqlite3.Connection, now: datetime) -> str:
    """Every (creator, source) pair's latest snapshot, sorted by |percent change| descending,
    with pairs that have no computable percent sorted last (D-11/D-12). Pure and
    fixture-testable — it reaches only into db.py, so nothing in the digest path imports the
    gateway or the Google client."""
    header = f"CreatorPulse digest — {now.date().isoformat()}"
    rows = db.fetch_latest_rows(conn)
    if not rows:
        return f"{header}\nNo rows recorded yet."

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

    lines = [header]
    for creator_id, source, views, prev_views, pct in sorted(computed, key=_sort_key):
        views_text = f"{views:,}" if views is not None else db.DELTA_PLACEHOLDER
        if pct is None:
            delta_text = db.DELTA_PLACEHOLDER
        else:
            # pct is not None only when both sides are ints and prev_views != 0.
            assert views is not None and prev_views is not None
            delta_text = f"{views - prev_views:+,}, {format_percent(pct)}"
        lines.append(f"{creator_id} / {source} — {views_text} views (Δ {delta_text})")
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
