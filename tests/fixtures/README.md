# Fixtures

Recorded API/scrape responses live at `tests/fixtures/{source}/{case}.{ext}` — e.g.
`tests/fixtures/youtube/channel_ok.json`, `tests/fixtures/tiktok/profile_ok.html`.

Files here are written by `scripts/record_fixture.py` (hand-run, never by pytest) and read by
the test suite. Never fetched at test time.
