# Pitfalls Research

**Domain:** Unattended daily metrics collector — Python 3.12, systemd timer, SQLite, gspread, Playwright, discord.py, single Linux VPS
**Researched:** 2026-07-29
**Confidence:** HIGH (systemd, SQLite, gspread quotas, YouTube quota costs, discord.py intents — verified against current official docs) / MEDIUM (Twitch Helix follower auth trap, Playwright OOM thresholds — verified via docs + community reports, numbers are approximate)

## Critical Pitfalls

### Pitfall 1: Script works when run by hand, fails silently under systemd

**What goes wrong:**
`python collect.py` works perfectly at the terminal. Under the timer it fails or behaves differently — wrong `cwd` so `creators.yaml`/`.env` aren't found, `PATH` missing so a subprocess (`playwright`, `chromedriver`) isn't found, `HOME` unset so Playwright can't find its browser cache dir, no TTY so anything expecting interactive input hangs.

**Why it happens:**
systemd services run in a minimal environment: no shell profile (`.bashrc`/`.profile` never sourced), no inherited shell `PATH`, `cwd` defaults to `/` unless set, and `HOME` is not guaranteed to be set for non-login service users.

**How to avoid:**
- Set `WorkingDirectory=/opt/creatorpulse` (or wherever the repo lives) explicitly in the `.service` unit — never rely on default cwd.
- Set `Environment=HOME=/home/creatorpulse` (or wherever the service user's home is) explicitly if Playwright or anything else needs `HOME`.
- Use absolute paths everywhere in code (venv python, config file, sqlite db path) — resolve relative to `Path(__file__).parent`, don't rely on cwd.
- Use `EnvironmentFile=/opt/creatorpulse/.env` for secrets, and reference the venv's python explicitly in `ExecStart=/opt/creatorpulse/.venv/bin/python collect.py` — don't rely on `PATH` for the interpreter.
- Run `User=creatorpulse` (a dedicated non-root user matching the VPS phase's UFW/SSH hardening), not root.

**Warning signs:** `systemctl start creatorpulse.service` (manual trigger) exits non-zero or logs `FileNotFoundError`/`ModuleNotFoundError` that never happens interactively. Test with `systemd-run --uid=creatorpulse --gid=creatorpulse env -i /opt/creatorpulse/.venv/bin/python collect.py` to reproduce the stripped environment before trusting the real timer.

**Phase to address:** Phase 1 (VPS/systemd setup) — write the unit file with explicit `WorkingDirectory`, `EnvironmentFile`, `User`, absolute `ExecStart` path, and test with `systemctl start` (not just interactively) before Phase 2 code lands.

---

### Pitfall 2: OnCalendar typo or Persistent= misunderstanding silently produces "never ran" or "ran three times at once"

**What goes wrong:**
Two distinct failures: (a) an `OnCalendar=` expression that parses but doesn't mean what you think (e.g. `*-*-* 07:00` fires every day at 7:00 UTC, not local time, unless `TimeZone=` is set on the timer, or `Mon..Fri` typo'd as `Mon-Fri` which is also valid but easy to get backwards on weekend intent); (b) assuming `Persistent=true` reruns *missed* runs on a fixed schedule catch-up basis, when it actually just means "if the system was off when the timer should have fired, run it once at next boot" — it does not replay every missed occurrence, and it does not fire immediately if the system was already up (only relevant across downtime).

**Why it happens:**
`OnCalendar` syntax is calendar-spec, easy to misread; timers default to UTC unless the unit or system timezone says otherwise; `Persistent=` semantics are non-obvious from the name alone.

**How to avoid:**
- Validate the calendar spec before deploying: `systemd-analyze calendar 'OnCalendar-expression-here'` prints the next 5 trigger times — always run this and eyeball it.
- Set `TimeZone=` explicitly in the timer unit if local time matters (e.g. `TimeZone=Asia/Manila`), or just standardize on UTC everywhere including in the `metric_date` column (see Pitfall 12) so there's no ambiguity to get wrong.
- Set `Persistent=true` so a VPS reboot or maintenance window doesn't silently skip the day entirely, but understand it fires once at next boot, not a backfill of every missed day.
- Add `RandomizedDelaySec=300` (a few minutes) so the job doesn't hammer external APIs at the exact same second as every other cron-like job on the box, and so repeated demo runs don't all collide on the same rate-limit window.

**Warning signs:** `systemctl list-timers` shows `NEXT` and `LAST` columns — if `LAST` never updates day over day, the timer isn't firing. `journalctl -u creatorpulse.timer` shows activation events independent of the service's own logs.

**Phase to address:** Phase 1 (VPS/systemd) — validate with `systemd-analyze calendar` before considering the phase done; Phase 6 (reliability/docs) re-verifies `Persistent=` behavior by simulating a missed run (stop the VPS across a scheduled fire time, confirm catch-up).

---

### Pitfall 3: Sheet never shared with the service-account email — first-time gspread failure, 100% of the time

**What goes wrong:**
`gspread.service_account()` authenticates fine, `client.open_by_key(sheet_id)` throws `gspread.exceptions.APIError: 403 PERMISSION_DENIED` or `SpreadsheetNotFound`. This is the single most common first-run gspread failure and it has nothing to do with code.

**Why it happens:**
A service account is its own "user" with its own email address (`xxx@project-id.iam.gserviceaccount.com`, found in the downloaded JSON key's `client_email` field). Creating the credentials does not grant it access to any specific Sheet — the Sheet must be explicitly shared with that email address (Editor access) exactly like sharing with a human collaborator.

**How to avoid:**
- After creating the service account and downloading its JSON key, open the target Google Sheet's Share dialog and add the `client_email` value as an Editor.
- Fail fast and legibly: wrap the first `open_by_key` call in a check that surfaces "Share the Sheet with <service-account-email> as Editor" rather than a bare stack trace, since this is the #1 thing to re-explain if the interviewer asks "what's the first thing that breaks."

**Warning signs:** 403 on the very first Sheets write attempt, working credentials otherwise (e.g. `gspread.service_account()` itself doesn't throw).

**Phase to address:** Phase 3 (Playwright + Sheets) — document this as the first manual step before writing any Sheets code, and write a one-line startup check that reads the `client_email` from the key file and prints it in an error message if the open fails.

---

### Pitfall 4: Cell-by-cell writes blow the Sheets API rate limit and are slow even under the limit

**What goes wrong:**
Looping over creators and calling `worksheet.update_cell(row, col, value)` or `worksheet.update('A1', value)` once per cell turns a ~10-creator Dashboard update into 30–50+ individual API calls. Each is a full HTTP round-trip subject to the same quota as a bulk write.

**Why it happens:**
It's the most obvious way to write the loop, and it "works" during manual testing with 2 rows before quota limits or noticeable latency show up.

**How to avoid:**
- Build the full 2D array (or list of `{"range": ..., "values": ...}` dicts) in memory first, then write once with `worksheet.update(range_name, values)` for a single contiguous block, or `spreadsheet.values_batch_update(body)` / `worksheet.batch_update(list_of_updates)` for multiple non-contiguous ranges in one HTTP call.
- For the append-only History tab, use `worksheet.append_rows(rows, value_input_option='USER_ENTERED')` (plural, batched) not a loop of `append_row`.

**Warning signs:** Sheets sync visibly takes multiple seconds per creator; `429` errors appear only once creator count grows past a handful, not during small-scale dev testing — meaning it'll surface for the first time during the live demo unless deliberately load-tested with the full creator list beforehand.

**Phase to address:** Phase 3 (Playwright + Sheets) — the Dashboard/History writer must be built batched from the first commit; this is already a Key Decision in PROJECT.md, but the concrete API call shape (`batch_update`/`values_batch_update`, not `update_cell` in a loop) is the part worth stating explicitly in the plan.

---

### Pitfall 5: RAW vs USER_ENTERED value_input_option silently breaks dates/percentages/deltas

**What goes wrong:**
`gspread`'s underlying Sheets API write calls take a `value_input_option` of `RAW` or `USER_ENTERED`. With `RAW`, a value like `"+5.2%"` or a date string is stored as a literal string — no formula evaluation, no type coercion — so conditional formatting rules keyed on numeric comparison silently do nothing, and a value meant to look like `=B2-B1` is stored as the text `=B2-B1` instead of computing. With `USER_ENTERED`, Sheets parses the input the way a human typing into a cell would (numbers become numbers, `%` suffixed strings become formatted percentages, date-looking strings become dates) — but this also means a creator name like `"1/2"` could get auto-converted to a date if typed carelessly.

**Why it happens:**
The default in raw `gspread` calls is not always the one the developer expects, and the two modes look identical for plain text values, so the bug only appears once numeric/date columns are involved (the delta column, the date column) — exactly the columns this project's Dashboard depends on for conditional formatting.

**How to avoid:**
- Use `value_input_option='USER_ENTERED'` for the Dashboard's numeric delta and date columns so conditional formatting (built in Apps Script, Phase 4) can key off real numbers/dates, not strings.
- Use `RAW` only for columns that must stay literal text no matter what they look like (e.g. a channel handle starting with a digit).
- Write one manual check at the end of Phase 3: open the Sheet and confirm the delta column is right-aligned (numeric) not left-aligned (text) in Google Sheets' default rendering — a 5-second visual proof the option was set correctly.

**Warning signs:** Conditional formatting rules (built in Phase 4) never trigger despite values "looking" right in the cell; delta values are left-aligned instead of right-aligned.

**Phase to address:** Phase 3 (Playwright + Sheets) for the write call; Phase 4 (Apps Script) verification depends on this being right, so the manual E2E check at the end of Phase 3 must confirm cell types before Apps Script work begins.

---

### Pitfall 6: A full-tab rewrite clobbers human-entered data and formatting

**What goes wrong:**
The Dashboard tab has a human-editable "Status" column (per PROJECT.md, editing it triggers a Discord webhook via `onEdit`). If the daily collector writes the Dashboard by clearing the whole tab (`worksheet.clear()`) and rewriting every column including Status, it destroys whatever the human just set, and it also wipes any manual formatting/column widths not recreated by the write.

**Why it happens:**
"Just clear and rewrite" is the simplest mental model for "sync a view," and it's fine for the append-only History tab but wrong for the editable Dashboard.

**How to avoid:**
- Write the Dashboard by column range, not full-tab clear: update only the metric columns (`values`, `deltas`, `last_updated`) via a targeted range like `Dashboard!B2:F11`, leaving column A (creator name, static) and the Status column untouched.
- Never call `.clear()` on the Dashboard tab from the collector. Reserve full-tab writes for the append-only History tab where there is nothing human-entered to lose.
- If a column ever needs to be reordered, do it as a deliberate one-time migration, not part of the daily write path.

**Warning signs:** Status column resets to blank/default after a collector run; Discord webhook fires unexpectedly right after a Sheet sync (because the collector's write triggered `onEdit` on a column it shouldn't have touched).

**Phase to address:** Phase 3 (Playwright + Sheets) — design the write function to take an explicit column range from the start; Phase 4 (Apps Script `onEdit`) should ideally scope its trigger to the Status column's range specifically so a metrics-column write can never accidentally fire it (`e.range.getColumn()` check inside `onEdit`).

---

### Pitfall 7: Playwright OOM-kills the collector on a small VPS, or never runs at all because deps/browsers aren't installed for the service user

**What goes wrong:**
Two distinct failures. (a) `playwright install chromium` was run interactively as one user (e.g. root or a dev login) but the systemd service runs as a different user (`creatorpulse`) whose `HOME` doesn't contain the downloaded browser binaries — the collector fails with "Executable doesn't exist" the first time it runs unattended, never having failed in manual testing under the dev's own account. (b) Chromium (even headless) can consume 300–500MB+ per instance; on a 1GB RAM VPS with no swap, running Chromium alongside SQLite, Python, and any other resident service (the Discord bot) risks the OOM killer silently killing the browser process (or the whole Python process) mid-run, with no clean exception — just a truncated/failed run.

**Why it happens:**
Playwright's browser binaries and OS-level shared libraries (`libnss3`, `libatk`, etc. — this is what `playwright install-deps` installs, separately from `playwright install`) are stored per-user by default and are easy to install once as whoever's logged in and forget the service user needs its own copy or a shared location; and headless Chromium's memory footprint is easy to underestimate on a small VPS sized for a lightweight Python job.

**How to avoid:**
- Run both `playwright install chromium` and `playwright install-deps` as the actual service user (`creatorpulse`), or install to a system-wide location and grant read access, then verify by running `systemd-run --uid=creatorpulse ... playwright --version` style checks — not just running it as the interactive/dev user.
- Always launch with `--no-sandbox` only if actually needed (prefer not, since the service user already isn't root) and always explicitly close the browser context and browser (`context.close()`, `browser.close()`) in a `finally`/`with` block so a crash mid-scrape doesn't leave a zombie Chromium process holding memory.
- Add a provision swap file (even 1–2GB) on the VPS as cheap insurance against transient memory spikes — this is a VPS-phase decision, not application code, and worth mentioning explicitly since the box may be sized minimally.
- Cap concurrency to one browser context at a time (sequential creators, not parallel) — this project has ≤3 sources and does not need concurrent scraping; concurrency is the multiplier that turns "fits in 1GB" into "doesn't."

**Warning signs:** Collector works when triggered manually by the dev but fails under `systemctl start` with "Executable doesn't exist at ..."; `dmesg` or `journalctl -k` shows `Out of memory: Killed process` entries correlated with collector run times; leftover `chrome`/`chromium` processes visible in `ps aux` after a crashed run that never call `browser.close()`.

**Phase to address:** Phase 1 (VPS) — provision swap and note the memory budget; Phase 3 (Playwright + Sheets) — install as the service user, always teardown in `finally`, sequential (not concurrent) creator scraping, and a manual `systemctl start` test (not just interactive) before considering the phase done.

---

### Pitfall 8: A page-structure change on the scraped TikTok profile returns `None` instead of raising — the run "succeeds" with garbage or missing data

**What goes wrong:**
A CSS/data-attribute selector that matched during development stops matching after a page redesign (or because a public profile page rendered a JS-shell with no content — see Pitfall 9). Playwright's `page.locator(...).text_content()` (or similar) can return `None` or an empty string instead of throwing, so a naive parser writes `None`/`0`/empty string into SQLite as if it were a legitimate reading — which then also breaks delta math (Pitfall 12) by looking like a real drop to zero.

**Why it happens:**
Locator-based extraction is designed to be lenient (part of Playwright's auto-waiting model) so a missing element doesn't always throw where a strict CSS selector query would.

**How to avoid:**
- Never trust an extracted value that is `None`/empty as a legitimate metric. Explicitly validate: if the expected numeric field can't be parsed to an `int`/`float`, raise a source-specific exception (e.g. `ScrapeParseError`) rather than writing a null-shaped record — this feeds directly into the failure-isolation requirement already in PROJECT.md ("one source failing does not kill the run").
- Use `expect(locator).to_be_visible(timeout=...)` or `locator.wait_for(state="attached")` before extracting, so a genuinely missing element throws a clear timeout error in the logs rather than silently returning nothing.
- Keep the saved HTML fixture (used in tests, per PROJECT.md's fixture-only testing rule) refreshed periodically by hand and treat a real production parse failure as a signal to look at the live page structure, not just re-run.

**Warning signs:** A metric that's always exactly `0` or always identical to the prior day's value for one source only; a test suite that's green against the fixture while the live source silently fails in production (fixture rot — see Pitfall 15).

**Phase to address:** Phase 3 (Playwright + Sheets) — parsing functions raise on missing/unparseable fields, never return sentinel `None`/`0`; Phase 2 (collector core) failure-isolation wrapper catches and logs the raised exception per-source without killing the run.

---

### Pitfall 9: A public profile page returns a JS-rendered empty shell instead of content — scraping "succeeds" against nothing

**What goes wrong:**
Playwright loads the page and `page.content()` returns valid HTML, but it's the pre-hydration skeleton (empty `<div id="root">` or similar) because the real data loads via a client-side XHR/GraphQL call after initial paint, or because `page.goto()` returned before that async content arrived.

**Why it happens:**
Many modern SPA-style profile pages defer content past the `load`/`domcontentloaded` event; a fixed `page.goto(url)` with default wait conditions doesn't guarantee the actual metric text is in the DOM yet.

**How to avoid:**
- Wait on the specific element that carries the metric (`page.wait_for_selector(selector, timeout=15000)`), not just page load state, before extracting.
- Set an explicit, generous-but-bounded timeout (e.g. 15–20s) per page — long enough for a slow VPS/network to render, short enough that one hung page doesn't stall the whole run past a reasonable ceiling. Wrap the whole per-creator scrape in a timeout so one hang can't block the other sources.
- If a source's public page cannot be scraped without waiting on JS execution that itself depends on non-public API calls or session state, per the hard constraint in this project's non-goals, the correct move is to drop that source rather than work around it — this is explicitly what the "3-source cap" and "official API first" decisions in PROJECT.md exist to avoid.

**Warning signs:** Extracted value is empty/`None` (see Pitfall 8) but the raw HTML dump (kept during development, never in prod) shows a loading spinner or skeleton markup instead of the real number.

**Phase to address:** Phase 3 (Playwright + Sheets).

---

### Pitfall 10: SQLite "database is locked" between the long-lived Discord bot (reader) and the periodic collector (writer)

**What goes wrong:**
SQLite by default allows one writer at a time and, in its default journal mode, a writer can block readers (and vice versa) long enough to produce `sqlite3.OperationalError: database is locked` — which is very plausible here since the Discord bot is a long-lived process potentially reading (`/creator`, `/status` commands) at the same moment the systemd-timer collector process writes its daily batch.

**Why it happens:**
Default SQLite journal mode (`DELETE`/rollback journal) takes an exclusive lock during writes that blocks concurrent readers; with two separate OS processes (bot + collector) accessing the same `.db` file, a query issued by either at the wrong moment can throw immediately rather than wait.

**How to avoid:**
- Enable WAL mode once, at setup: `PRAGMA journal_mode=WAL;` — WAL allows concurrent readers alongside a single writer without blocking reads, which is exactly this project's read (bot) + write (collector) shape.
- Set a busy timeout on every connection: `PRAGMA busy_timeout=5000;` (or pass `timeout=5` to `sqlite3.connect()`) so a transient lock retries for up to N seconds instead of raising immediately — this covers the rare moment both processes touch the DB in the same instant even under WAL.
- Keep collector transactions short (batch the whole run's writes into one `commit()`, or a few, not one commit per row) so the writer holds any lock for the shortest possible window.

**Warning signs:** `/status` or `/creator` occasionally throws `database is locked` specifically around the timer's scheduled fire time and nowhere else — timing-correlated errors are the tell.

**Phase to address:** Phase 2 (collector + SQLite) sets `WAL` mode and `busy_timeout` in the connection-setup code shared by both the collector and the bot (one shared `db.py` module, not duplicated connection logic) so neither process can be brought up without it.

---

### Pitfall 11: Naive INSERT breaks re-runnability — re-running the same day duplicates rows or throws on the second run

**What goes wrong:**
A plain `INSERT INTO metrics (...) VALUES (...)` run twice for the same creator/source/day either duplicates the row (if there's no uniqueness constraint) or throws an unhandled `IntegrityError` (if there is a constraint but the code doesn't handle the conflict) — either way, a demo re-run (very likely, since the interview will probably include "run it again for me") breaks the idempotency test PROJECT.md already requires.

**Why it happens:**
`INSERT` is the default mental model; upsert semantics require deliberately opting in.

**How to avoid:**
- Define the table with `UNIQUE(creator_id, source, metric_date)` (already a Key Decision in PROJECT.md) and write every insert as `INSERT INTO metrics (...) VALUES (...) ON CONFLICT(creator_id, source, metric_date) DO UPDATE SET value=excluded.value, ...` (SQLite's `ON CONFLICT` upsert syntax, available since SQLite 3.24, well within Python 3.12's bundled SQLite version).
- The idempotency test already planned (run collector twice, assert row count unchanged) is the correct verification — but also assert the *value* updates on the second run if the underlying number changed intraday, not just that the row count didn't grow.

**Warning signs:** Row count in `metrics` grows on a second identical-day run; `sqlite3.IntegrityError: UNIQUE constraint failed` surfaces unhandled in logs.

**Phase to address:** Phase 2 (collector + SQLite) — schema and write path both built with `ON CONFLICT ... DO UPDATE` from the first commit, verified by the idempotency test already scoped in PROJECT.md.

---

### Pitfall 12: `metric_date` ambiguity — UTC vs local, midnight-slip runs, and DST-adjacent bugs corrupt "day-over-day" delta math

**What goes wrong:**
The Dashboard's day-over-day delta depends on `metric_date` meaning exactly one thing. If the collector uses `datetime.now()` (naive, local time) for one part of the code and `datetime.utcnow()` elsewhere, or if the timer fires close enough to local midnight that a slow run (e.g. Playwright timeouts stacking up) crosses into the next calendar day mid-run, two creators in the same run can get different `metric_date` values, or a whole run can silently get "the wrong day" stamped — invisible until the delta column shows a nonsensical jump or a flat zero.

**Why it happens:**
"Today" is a local-time human concept but the underlying clock and any UTC-based systemd timer don't automatically agree with it, and Python's naive vs aware datetime handling makes it easy to mix `datetime.now()` and `datetime.utcnow()` without noticing (both compile, both look "date-shaped").

**How to avoid:**
- Pick UTC as the canonical `metric_date` basis, decided once, applied everywhere: compute `metric_date = datetime.now(timezone.utc).date()` once at the *start* of the run and pass that single value through to every write in that run — never recompute "today" per-source or per-creator, so a slow run can't straddle midnight and split across two dates.
- If the timer itself is scheduled in local time via `TimeZone=` in the unit (see Pitfall 2), document explicitly in the README/build journal which is canonical (recommend: schedule the timer in local time for a human-friendly "runs every morning," but store `metric_date` in UTC — and say so explicitly wherever dates are displayed, e.g. Discord `/status`, so there's no silent mismatch to explain badly in the interview).
- Store all timestamps (`run start`, `run end` in the `runs` table) as UTC ISO-8601 strings (`datetime.now(timezone.utc).isoformat()`), never naive `datetime.now()`.

**Warning signs:** Two rows for the same creator/source with dates one day apart when only one run happened; delta calculations occasionally showing an extra day's gap or a repeated day.

**Phase to address:** Phase 2 (collector + SQLite) — `metric_date` computed once per run and threaded through, not recomputed; covered implicitly by the idempotency test but worth a dedicated assertion that all rows from one run share one `metric_date`.

---

### Pitfall 13: NULL vs 0 corrupts delta math

**What goes wrong:**
If a source fails and its record is skipped (correct, per PROJECT.md's failure-isolation requirement) but the delta calculation (in Apps Script or in the collector before writing the Dashboard) treats a missing prior-day row as `0` instead of "no comparison available," the Dashboard shows a delta like "+1,204,000" (current subs minus zero) instead of "no data yesterday" — a wildly wrong number that looks plausible enough to embarrass the demo.

**Why it happens:**
`COALESCE(value, 0)`-style defensive coding is a common reflex to avoid `NULL` propagating through arithmetic, but it's wrong here specifically because `0` is a valid subscriber/follower count concept while `NULL` (no row) is not the same thing as "the count is zero."

**How to avoid:**
- Compute the delta only when both today's and yesterday's rows exist for that `(creator_id, source)`; if either is missing, write/display an explicit "—" or "N/A", never a computed number against an assumed zero.
- In SQL, prefer a `LEFT JOIN` on yesterday's row and check `IS NULL` explicitly rather than defaulting via `COALESCE` into arithmetic.

**Warning signs:** A delta value equal to the full current metric value (the tell that "yesterday" was treated as 0).

**Phase to address:** Phase 2 (collector + SQLite) for the underlying data shape; Phase 3/4 (Sheet writer / Apps Script) for the delta display logic — whichever layer computes the delta must branch on missing-row, not coalesce.

---

### Pitfall 14: discord.py — missing privileged intents, or a blocking call inside an async handler freezes the whole bot

**What goes wrong:**
Two distinct failures. (a) `/creator` and `/status` are slash commands and don't need the Message Content or Members privileged intents at all — but if the bot code enables `intents.message_content = True` (common copy-pasted boilerplate) without also toggling "Message Content Intent" in the Discord Developer Portal, the bot fails to connect at startup with a `PrivilegedIntentsRequired` error — a portal/code mismatch, not a code bug, and exactly the kind of gap PROJECT.md flags as the author's responsibility to understand. (b) Any blocking call (`time.sleep()`, a synchronous `requests.get()`, a synchronous SQLite query without `run_in_executor`) inside an `async def` command handler blocks discord.py's single event loop, freezing every other command and the heartbeat to Discord — which after enough delay causes Discord to consider the connection dead and disconnect the bot.

**Why it happens:**
Intents must match in two places (code flags and Developer Portal toggles) and it's easy to enable one without the other; async code that "happens to work" with blocking calls at low load masks the freeze until a slow SQLite read (e.g. during a concurrent collector write, see Pitfall 10) coincides with a live demo.

**How to avoid:**
- Only request the intents actually needed. This project's slash commands (`/creator`, `/status`) and a scheduled digest post need `intents.default()` (or even less) — no Members or Message Content intent required, so don't enable them and don't need to toggle them in the Portal. State this explicitly in the build journal since it's a specific, checkable claim to make in the interview.
- Any SQLite read/write inside a command handler should either be fast enough not to matter (SQLite local reads are sub-millisecond normally) or explicitly run via `await bot.loop.run_in_executor(None, blocking_fn)` if it risks blocking (e.g. during a lock-contention retry, see Pitfall 10's `busy_timeout`).
- Never use `time.sleep()` in a command coroutine; use `await asyncio.sleep()`.

**Warning signs:** Bot fails to log in at all with a `PrivilegedIntentsRequired` traceback (intents mismatch); bot appears "online" in Discord but stops responding to any command for tens of seconds (blocking call).

**Phase to address:** Phase 5 (Discord bot) — request minimal intents matching what's actually toggled in the Developer Portal (human-owned per PROJECT.md); Phase 6 (reliability) load-tests a command during a concurrent collector run to confirm no freeze.

---

### Pitfall 15: Slash command registration propagation delay makes a working command look broken during rehearsal

**What goes wrong:**
Globally-registered slash commands (`bot.tree.sync()` with no guild ID) can take up to an hour to propagate to Discord's client caches; a command registered minutes before a demo/rehearsal may not show up in the command autocomplete yet, even though the bot and code are correct.

**Why it happens:**
Global command sync is deliberately rate-limited/cached by Discord; only guild-scoped sync (`bot.tree.sync(guild=discord.Object(id=GUILD_ID))`) is near-instant.

**How to avoid:**
- During development and for the interview demo itself, sync commands to a specific guild (the test/demo server) rather than globally — near-instant propagation, and no risk of a stale command list during rehearsal.
- Only consider global sync if the bot needs to serve multiple unknown servers, which is out of scope here (single operator, single machine, per PROJECT.md).

**Warning signs:** A newly added/changed slash command doesn't appear (or an old signature still shows) in Discord's command picker shortly after a code change and restart.

**Phase to address:** Phase 5 (Discord bot) — use guild-scoped command sync from the start, not global.

---

### Pitfall 16: A service-account JSON key or `.env` gets committed before `.gitignore` exists

**What goes wrong:**
The very first `git init`/first commit happens before `.gitignore` lists `.env` and `*.json` credential files, so the service-account key or Discord bot token lands in git history on commit #1. Deleting the file in a later commit does not remove it from history — anyone who clones the repo (or a public GitHub push) can still recover it from an earlier commit.

**Why it happens:**
`.gitignore` is easy to treat as a "nice to have early" step instead of a hard prerequisite to the first `git add`.

**How to avoid:**
- Write `.gitignore` (including `.env`, `*.json` service-account key patterns, `__pycache__/`, `.venv/`) as the literal first file in the repo, before running `git add` on anything else — this is already stated as a constraint in PROJECT.md ("`.gitignore` written before the first commit").
- If a secret is ever committed despite this: treat it as compromised. The fix is rotation, not deletion — regenerate the Google service-account key (delete the old key in Google Cloud Console, create a new one) and regenerate the Discord bot token (Developer Portal → Bot → Reset Token), then update the local `.env`/`EnvironmentFile`. Do not rely on `git filter-branch`/`BFG` history rewriting as the fix by itself — if the repo was ever pushed anywhere, the old secret must be treated as permanently exposed regardless of history rewrites.

**Warning signs:** `git log --all --full-history -- '*.env' '*.json'` (run once, before the first push, as a habit) returns any hits.

**Phase to address:** Phase 0 (skeleton) — `.gitignore` is the first file written, before any other `git add`.

---

### Pitfall 17: Fixture-based tests rot silently when the live source changes, or an agent weakens a test to reach green

**What goes wrong:**
Tests assert against saved HTML/JSON fixtures (correct, per PROJECT.md's no-live-network-in-tests rule), but if the live YouTube/Twitch/TikTok response shape changes (a new field, a renamed key, a restructured DOM), the fixture-based suite stays green forever while production silently breaks — the tests prove nothing except "the parser still parses last month's snapshot." Separately, under time pressure an agent (or a rushed human) asked to "make the test pass" may loosen an assertion (e.g. change an exact-value check to a type-only check, or comment out a failing assertion) instead of fixing the actual bug — passing tests that no longer test anything.

**Why it happens:**
Fixtures are static by design (that's the point — no live calls in tests) so nothing forces a periodic re-check against reality; and "green" is the visible success signal that's easiest to chase directly instead of fixing root cause.

**How to avoid:**
- Assert on specific extracted fields with expected values (`assert record["subscriber_count"] == 152000`), never on "a full record dict returned without error" or "the dict has these keys" alone — a test that only checks key presence would pass even if every value were silently wrong.
- Periodically (a manual step, not automated, given the 7-day scope) re-save one real fixture snapshot and diff it against the one in the repo to catch drift by eye — this is a cheap, honest thing to say happened once in the build journal.
- Per PROJECT.md's own guard: diff test files on every iteration during Verify; treat any test file change as suspect unless explicitly requested. Concretely: `git diff` the test files before accepting a "tests pass" claim from an agent, and reject any diff that loosens an assertion (removes a specific expected value, widens a type check, adds a `# TODO` skip) without an explicit reason logged in the build journal.

**Warning signs:** A test suite that's 100% green while the live source is known to have changed recently (e.g. a site redesign); an agent's diff shows a test assertion got weaker, not the implementation getting more correct.

**Phase to address:** Phase 2 (collector core, general testing pattern) sets the "assert specific values, not shape" convention; Phase 3 (Playwright fixtures) is where fixture rot risk is highest given a scraped source; enforced continuously via the Verify step's test-diff check already specified in PROJECT.md.

---

### Pitfall 18: Interview-day live-demo failure modes that never show up in solo dev testing

**What goes wrong:**
Several failure modes are dormant during solo development and specifically appear under "run it in front of someone" conditions: (a) cold-start — the timer hasn't fired in hours/days by demo time, so a live "let's watch it run" moment requires either waiting for the real schedule or a manual `systemctl start creatorpulse.service` trigger, which the author should rehearse, not discover live; (b) a source gets rate-limited from the author's own repeated manual test runs earlier that day/week (YouTube's 10,000-unit daily quota, Twitch's per-minute bucket) so the "real" demo run returns a 429/quotaExceeded specifically because of rehearsal, not because anything is broken; (c) an expired/near-expired Twitch app access token (see Pitfall 19) causes a 401 mid-demo if the token was minted days earlier and never refreshed; (d) the Sheet shows yesterday's numbers looking perfectly fine because a sync failed silently earlier (swallowed exception, no alert) rather than loudly.

**Why it happens:**
Demos are, by construction, the first time the full unattended path is watched end-to-end under time pressure, and rehearsal itself consumes quota/tokens that the real demo then needs.

**How to avoid:**
- Have a manual trigger command memorized and rehearsed (`sudo systemctl start creatorpulse.service`) rather than waiting on the timer live, and know how to tail it live (`journalctl -u creatorpulse.service -f`) so "watch it run" is instant and visibly logged.
- Track quota burn deliberately: YouTube's 10,000-unit/day budget is easily exhausted by repeated manual dev-testing on the same day as the demo (each `channels.list` call is cheap at 1 unit per PROJECT.md's ≤3-source, few-creator scale, but forgetting this and calling `search.list` anywhere, at 100 units/call, is the one call that could actually matter — avoid `search.list` entirely; resolve channel IDs once via `forHandle` and cache the ID in `creators.yaml`, not re-resolved every run).
- Never let a Sheet-sync or Discord-post failure fail silently: the `runs` table (already required by PROJECT.md) must record failure count, and the Discord `/status` command must be able to show "last successful sync: N hours ago" — so a stale Sheet during a demo is immediately explainable and visible, not a silent mystery the author has to improvise around.
- The morning of the interview, do a full manual dry run early (not late) so token/quota state is known-fresh, then avoid further manual triggers until the actual scheduled/demo run.

**Warning signs:** N/A by definition (this pitfall is about first-occurrence-under-observation) — the entire point is that rehearsal must surface these, so rehearse the trigger and the logs-watching step at least once before interview day.

**Phase to address:** Phase 6 (reliability/docs) — this is exactly what that phase is for: rehearse the manual trigger, verify `/status` surfaces staleness/failure honestly, and do a dry run early on interview day itself.

---

### Pitfall 19: Twitch app access token (client_credentials) is minted once and never refreshed — 401 at 3am, or the follower-count endpoint returns nothing useful

**What goes wrong:**
Two distinct traps. (a) An app access token from `POST https://id.twitch.tv/oauth2/token` (client_credentials grant) has a finite lifetime (on the order of ~days-to-months, and Twitch can invalidate it early); code that fetches the token once at process startup and holds it in memory forever will eventually get a `401 Unauthorized` on an unattended run with no human present to notice and re-auth. (b) Twitch's Get Channel Followers endpoint has changed: without a broadcaster-scoped user token carrying `moderator:read:followers` (which an app-only `client_credentials` token cannot provide — that scope requires a user to have authorized it), the endpoint returns only the aggregate `total` follower count in the response and no follower list — which happens to be exactly the metric this project needs (a count, not a list), but it is not retrievable at all with a bare app access token in every historical version of this endpoint, so this must be verified directly against current Twitch docs for the specific field being read, not assumed to still work the way older tutorials describe.

**Why it happens:**
`client_credentials` app tokens are the natural choice for a script with no interactive user login step, and "get a token once" is the natural first implementation; Twitch has also progressively locked down follower data for privacy reasons (the older `users/follows` endpoint was deprecated and returns `410 Gone`), and tutorials/blog posts from before the change still describe the old, now-broken behavior.

**How to avoid:**
- Cache the app access token with its `expires_in` value and proactively refresh (re-request a new token) before expiry — e.g., refresh if `time.time() > token_acquired_at + expires_in - 300` (5-minute safety margin) — rather than waiting for a 401 to trigger a retry (though a 401-triggered re-auth-and-retry-once is a reasonable belt-and-suspenders addition, not a replacement for proactive refresh).
- Before building against the follower-count field, confirm directly in current Twitch developer docs (`dev.twitch.tv/docs/api/reference/#get-channel-followers`) exactly what an app-only token can retrieve — if the total count is genuinely accessible without a user-authorized scope, use it; if it isn't, that's a real, current API limitation to document in the build journal and in the README's honest-tradeoffs section (this is exactly the kind of engineering judgment PROJECT.md wants defensible in the interview) rather than something to route around with any kind of workaround token flow.
- Do not build any user-authorization/OAuth-flow (getting a broadcaster's own user token) for this — it's out of scope for a single-operator tool pulling public stats about creators who are not the tool's own account holder; if the follower count genuinely requires it, treat "this metric isn't available via public/app-only auth" as a legitimate, stated limitation rather than building the extra auth flow to route around it.

**Warning signs:** Twitch calls succeed for days/weeks then start failing with `401` with no code change (token expiry); a "follower count" field comes back present but showing only a `total` with no detail, or the field the code expects isn't in the response documented for app-only auth at all.

**Phase to address:** Phase 2/3 (Twitch source implementation) — token refresh logic built in from the start (not retrofitted after a 3am failure that will never actually be observed live, only inferred from the `runs` table's failure log); verify the follower-count field's actual auth requirement against current docs before writing the parser, not after.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|--------------------|-----------------|------------------|
| Single `.env` on the VPS shared by both bot and collector services | One file to manage | A leaked/rotated secret requires restarting both services in lockstep; harder to reason about which secret belongs to which process | Acceptable for this project's scale (single operator, two services) — just document which keys belong to which process in the README |
| No retry/backoff on 429s beyond a fixed sleep-and-retry-once | Simple to write | Repeated demo-day manual runs could still exhaust quota if backoff isn't real exponential backoff | Never for Sheets/YouTube/Twitch calls — implement real exponential backoff (even a minimal 3-attempt version), since 429s are explicitly documented as expected, not exceptional |
| Skipping Playwright's `context.close()`/`browser.close()` teardown "because the process exits anyway" | Slightly less code | Zombie Chromium processes accumulate across crashed runs, silently eating the VPS's limited RAM until the next reboot | Never — always teardown in `finally`, cheap to do correctly |
| Storing `metric_date` as a naive local-time string instead of deciding UTC-vs-local once | Feels natural, matches what a human reads | Silent delta corruption at exactly the boundary where it's hardest to debug (midnight, DST) | Never — decide once in Phase 2, thread through everywhere |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|--------------|------------------|--------------------|
| Google Sheets (gspread) | Forgetting to share the target Sheet with the service account's `client_email` | Share the Sheet as Editor with the service-account email immediately after generating credentials; fail loudly with that exact instruction if `open_by_key` 403s |
| Google Sheets (gspread) | Writing cell-by-cell in a loop | Build the full range in memory, write once via `update()`/`batch_update()`/`append_rows()` |
| Google Sheets (gspread) | Using `RAW` for numeric/date columns that conditional formatting depends on | Use `USER_ENTERED` for numeric/date columns; verify cell alignment visually as a smoke test |
| YouTube Data API v3 | Calling `search.list` to find a channel (100 units/call) instead of resolving via `forHandle` once and caching the channel ID | Resolve each configured creator's channel ID once via `channels.list(forHandle=...)`, store the resolved ID in `creators.yaml` or a cache table, never re-resolve every run |
| YouTube Data API v3 | Treating small day-over-day subscriber deltas as meaningful | `subscriberCount` is rounded to 3 significant figures above 1,000 subscribers — small deltas are noise from rounding, not real change; don't build UI/logic that implies false precision |
| Twitch Helix | Assuming an app-only (`client_credentials`) token can read anything a browser sees | Verify per-endpoint auth requirements against current docs; the follower endpoint in particular requires broadcaster/moderator user-token scope for anything beyond the total count |
| Twitch Helix | Minting a token once at process start and never refreshing | Track `expires_in`, refresh proactively before expiry with a safety margin |
| discord.py | Enabling `message_content`/`members` intents in code without the matching Portal toggle (or vice versa) | Only request intents actually needed for slash commands (none of the privileged ones, in this project's case); if a privileged intent truly is needed later, toggle it in the Portal first |
| SQLite | Two processes (bot + collector) sharing a DB file with default journal mode | `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=5000` set once in shared connection setup |
| systemd | Assuming the service inherits the interactive shell's `PATH`/`HOME`/cwd | Set `WorkingDirectory`, absolute `ExecStart` path, and `Environment=HOME=...` explicitly in the unit |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Cell-by-cell Sheets writes | Sync takes seconds per creator; fine at 2 test creators | Batch writes from the start | Breaks (429s, visible slowness) once creator count or write frequency grows past a handful — likely to surface during rehearsal/demo, not solo dev testing |
| Concurrent Playwright browser contexts | Works fine with 1 creator scraped, OOMs or thrashes with more | Sequential scraping, one browser context at a time, explicit teardown | Breaks on a 1GB VPS once more than ~1-2 concurrent Chromium instances are alive at once |
| `search.list` for channel resolution | Fine the first few times | Resolve once via `forHandle`, cache the ID | Breaks (quota exhausted) after ~100 calls in a day given the 10,000-unit budget |
| Naive per-cell SQLite commits in a loop | Fine at small row counts | Batch all of one run's writes into a single transaction/commit | Slower and holds write locks longer as row/creator count grows, worsening lock contention with the Discord bot reader |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Service-account JSON or bot token committed to git before `.gitignore` exists | Secret permanently recoverable from history even after later deletion, especially once pushed to a remote | Write `.gitignore` as literally the first file, before the first `git add`; if it happens anyway, rotate the credential (don't just delete the file) |
| `.env` file readable by other VPS users | A creator-metrics tool leaking a Discord bot token or Sheets key lets someone else post as the bot or edit the Sheet | `chmod 600` on the env file (already a stated constraint) and confirm ownership matches the service user, not just permissions |
| Running the collector/bot as root | Unnecessary blast radius if either dependency (Playwright's Chromium, a compromised package) is exploited | Dedicated non-root `creatorpulse` user for both systemd services, matching the VPS-hardening phase's non-root/UFW setup |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-------------------|
| Sheet shows stale numbers with no indication sync failed | Ops-team reader (or interviewer) trusts wrong numbers, has no idea a run failed | `/status` and/or a Dashboard "Last synced" cell that reflects the `runs` table honestly, updated whether the run succeeded or failed |
| Delta column shows a huge/nonsensical number when yesterday's data is missing | Looks like a real spike/crash, undermines trust in the whole tool during a demo | Missing-comparison rows show "—"/"N/A", never a computed delta against an assumed zero (Pitfall 13) |
| Discord digest posts with no clear "as of" timestamp | Ambiguous whether the numbers are from today's run or a stale cache | Always include the `metric_date`/run timestamp in the digest message itself |

## "Looks Done But Isn't" Checklist

- [ ] **Systemd timer:** Often "works" only because it was triggered manually as the dev's own user — verify with `systemctl start` as the actual service user/env, not just `python collect.py` at a terminal
- [ ] **Sheets writer:** Often looks done with 2 test rows written cell-by-cell — verify it still holds at the full creator list and doesn't regress into per-cell calls anywhere in the code path
- [ ] **Playwright source:** Often looks done against the saved fixture — verify it still parses the live page today, not last week's HTML snapshot, and confirm teardown actually releases the browser process (check `ps aux` after a deliberately-crashed run)
- [ ] **Idempotency test:** Often looks done by asserting "row count unchanged" — verify it also asserts values update correctly on a second run of the same day, and that `metric_date` is identical across every row from one run
- [ ] **Failure isolation:** Often looks done by wrapping one source's call in `try/except` — verify the `runs` table's failure count actually increments and the run's overall exit code/log still reflects the failure, so a "silent partial success" doesn't read as a clean run
- [ ] **Discord `/status`:** Often looks done by returning the last run's timestamp — verify it also surfaces failure count and staleness (e.g. "last successful sync was N hours ago"), not just "a run happened"

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|-----------------|-----------------|
| Secret committed to git history | MEDIUM | Rotate the credential immediately (new service-account key, new bot token) — do not rely on history rewriting alone if ever pushed anywhere |
| Sheet not shared with service account | LOW | Share the Sheet with the `client_email` as Editor; no data lost, just blocked until then |
| Full-tab clear wiped Status column | LOW–MEDIUM | If History tab retained the data, Status is cosmetic and gets re-set by a human; if not backed up anywhere, it's simply lost — low-stakes for a demo Sheet |
| Duplicate rows from a pre-`ON CONFLICT` naive INSERT bug | LOW | `DELETE` duplicates keeping the latest `rowid` per `(creator_id, source, metric_date)`, then add the constraint and switch inserts to upsert |
| Playwright zombie processes accumulated | LOW | `pkill -f chromium` (or restart the service) as an immediate fix; add proper teardown as the real fix |
| OOM-killed collector run mid-write | LOW–MEDIUM | Failure isolation + `runs` table failure logging means the next scheduled run naturally retries; no manual recovery needed if idempotency (Pitfall 11) is solid |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|--------------------|----------------|
| Script works interactively, fails under systemd | Phase 1 | `systemctl start` as service user succeeds, not just interactive run |
| OnCalendar/Persistent= misunderstanding | Phase 1 | `systemd-analyze calendar` output matches intent; `systemctl list-timers` shows correct `LAST`/`NEXT` |
| Sheet not shared with service account | Phase 3 | First `open_by_key` call succeeds without 403 |
| Cell-by-cell Sheets writes | Phase 3 | Code review confirms no per-cell `update_cell` in a loop; sync completes in one/few API calls for the full creator list |
| RAW vs USER_ENTERED | Phase 3 | Delta/date columns render right-aligned (numeric/date), not left-aligned (text) |
| Full-tab rewrite clobbers Status column | Phase 3 (write path) / Phase 4 (onEdit scoping) | Manually edit Status, run collector, confirm Status persists |
| Playwright deps/OOM/zombies | Phase 1 (swap) / Phase 3 (install-as-service-user, teardown) | `systemctl start` as service user succeeds; `ps aux` clean after a forced-crash test |
| Page structure change → silent `None` | Phase 3 | Parser raises on unparseable/missing field, verified by a fixture test that intentionally breaks a selector |
| JS-rendered empty shell | Phase 3 | Wait on the specific metric element, not just page load; bounded per-page timeout |
| SQLite "database is locked" | Phase 2 | `WAL` + `busy_timeout` set in shared `db.py`; bot query during a concurrent collector write doesn't throw |
| Naive INSERT breaks re-runnability | Phase 2 | Idempotency test (already required) passes: run twice, row count unchanged, values update correctly |
| metric_date UTC/local/midnight-slip | Phase 2 | All rows from one run share identical `metric_date`; computed once per run |
| NULL vs 0 in delta math | Phase 2 (data) / Phase 3–4 (display) | Missing-prior-day case shows "—", never a full-value delta |
| discord.py intents mismatch / blocking calls | Phase 5 | Bot connects cleanly with minimal intents; a command issued during a concurrent collector write doesn't freeze the bot |
| Slash command propagation delay | Phase 5 | Guild-scoped sync used, command appears immediately after restart |
| Secret committed before `.gitignore` | Phase 0 | `.gitignore` is the first file in the repo, before first `git add` |
| Fixture rot / weakened tests | Phase 2–3 (convention) / continuous (Verify) | Assertions check specific values, not just shape; test-file diffs reviewed on every Verify pass |
| Demo-day failure modes (cold start, quota burn, silent stale sync) | Phase 6 | Manual trigger rehearsed; `/status` proven to surface staleness/failure honestly; dry run done early on interview day |
| Twitch token expiry / follower-endpoint auth trap | Phase 2–3 | Token refresh logic present and tested; follower-count field's auth requirement confirmed against current docs before relying on it |

## Sources

- [Usage limits | Google Sheets API — developers.google.com](https://developers.google.com/workspace/sheets/api/limits) — HIGH confidence, official docs, fetched directly
- [Get Channel Followers / Twitch API Reference — dev.twitch.tv](https://dev.twitch.tv/docs/api/reference/) — HIGH confidence, official docs (cross-checked via search after direct fetch failed with connection reset)
- [Twitch Developer Forums — "Issue with channel followers endpoint"](https://discuss.dev.twitch.com/t/issue-with-channel-followers-endpoint/47423) — MEDIUM confidence, community confirmation of the scope-gated behavior
- [twitchdev/issues #1087 — `/users/follows` returning 410 Gone](https://github.com/twitchdev/issues/issues/1087) — MEDIUM confidence, confirms deprecation of the older endpoint
- [YouTube Data API — Channels: list (forHandle) — developers.google.com](https://developers.google.com/youtube/v3/docs/channels/list) — HIGH confidence, official docs
- [YouTube Data API — subscriberCount rounding, Rival IQ explainer](https://help.rivaliq.com/en/articles/9788197-why-youtube-subscriber-counts-are-rounded) — MEDIUM confidence, cross-checked against official channels-resource docs describing rounding to 3 significant figures
- [YouTube API quota cost discussion — dev.to, ChannelCrawler, SocialCrawl 2026 explainers](https://dev.to/qcrao/what-i-learned-squeezing-the-youtube-data-api-v3-quota-for-a-side-project-3304) — MEDIUM confidence, consistent across multiple independent sources on `channels.list` (1 unit) vs `search.list` (100 units) and the 10,000/day default budget
- systemd `systemd.timer`/`systemd.service` semantics (`Persistent=`, `OnCalendar`, `WorkingDirectory`, `EnvironmentFile`, `RandomizedDelaySec`) and SQLite `PRAGMA journal_mode=WAL`/`busy_timeout`/`ON CONFLICT` upsert syntax, gspread `value_input_option`, and discord.py intents/gateway behavior — HIGH confidence, drawn from stable, long-documented official behavior consistent with current man pages/docs; not independently re-fetched this session but not flagged as recently-changed in any surfaced source

---
*Pitfalls research for: unattended daily metrics collector (systemd + SQLite + gspread + Playwright + discord.py)*
*Researched: 2026-07-29*
