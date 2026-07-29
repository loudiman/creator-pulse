# API Coverage — Phase 1: Skeleton

No external API integration: Phase 1 ships packaging, a CLI shell, a parse-only `creators.yaml` reader,
one test, and the documented quality gate — it calls no platform API and contains no client for one.

The YouTube, Twitch, Google Sheets and Discord integrations are Phases 3, 4 and 6; their capability
matrices belong to those phases and must start from a full-coverage baseline there, not inherit
anything from here. The `requests`, `gspread`, `discord.py` and `playwright` packages appear in
`pyproject.toml` as version pins only (D-17) — no module in `src/` imports any of them in this phase.

`scripts/record_fixture.py` does make a live HTTP request, but it is a generic operator-run
fetch-and-save utility with no platform endpoint, no response parsing, and no browser automation. It
integrates nothing; it saves bytes to a path.
