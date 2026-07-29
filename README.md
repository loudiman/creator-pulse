# CreatorPulse

A daily creator-metrics collector that runs unattended on a rented Linux VPS. Every morning a
systemd timer fires a Python job that pulls public stats for a configured list of social media
creators, writes them with full history into SQLite, syncs a Google Sheet view, and posts a
summary to Discord. Nobody touches it.

**Phase 1 status:** this is the skeleton. `creatorpulse collect` exists, reads `creators.yaml`,
logs a full run, and exits 0 — but it does not collect anything yet. The real YouTube/Twitch/
TikTok collection body lands in Phase 3.

## Install

Development happens on Windows; deployment is a Linux VPS. Both need Python 3.12 exactly
(`requires-python = ">=3.12,<3.13"` in `pyproject.toml`).

### Windows (development)

```
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

Use `py -3.12` explicitly — bare `python` resolves to the Microsoft Store alias stub, and bare
`py` resolves to whatever the newest installed interpreter is, not necessarily 3.12. The quotes
around `".[dev]"` are required in PowerShell (and in zsh, for the Linux side below).

### Linux (VPS deployment)

```
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
```

The VPS installs the plain package only — no `[dev]` extra, so ruff, mypy and pytest never land
on the deployment box. Only local development installs the dev extra.

## The gate

This is the definition of green for every phase in this project. One fenced block, four commands,
same order, same result on Windows and on the VPS, with the venv active:

```
ruff format --check .
ruff check .
mypy src/
pytest
```

`ruff format --check .` is the fourth command — it catches formatting drift before it reaches a
diff, and `ruff format .` (without `--check`) is the fix. No Makefile and no paired per-platform
runner scripts exist here on purpose: `make` isn't on the Windows box, and a `check.sh`/`check.ps1`
pair would drift into a silent difference between the development gate and the deployment gate.
This documented block is the only definition of green there is.

## Usage

```
creatorpulse collect --config creators.yaml
```

`--config` defaults to `creators.yaml` at the repo root (`DEFAULT_CONFIG_PATH` in
`src/creatorpulse/config.py`) if omitted. `creatorpulse sync` and `creatorpulse bot` are stubs
that exit 3 until Phase 4 and Phase 6 fill them in.

## creators.yaml

One entry per creator:

```yaml
creators:
  - id: xqc
    name: xQc
    sources:
      youtube: "@xQcOW"
      twitch: xqc
      tiktok: "@xqc"
```

- `id` — a hand-written slug. Never change it once metrics rows exist; it's part of the
  database's unique key.
- `name` — display name.
- `sources` — a map from platform to the human-friendly identifier (a YouTube handle, a Twitch
  login, a TikTok username). Code resolves these to API identifiers at runtime.

Add a creator by editing this file. No code change required.

## Tests and fixtures

`pytest` runs against saved fixtures only — no live network calls in the suite. See
`tests/fixtures/README.md` for the `{source}/{case}.{ext}` convention and `scripts/record_fixture.py`
for the sanctioned (hand-run, never pytest-collected) way to record a new one.

## What's human-built

VPS provisioning and the systemd unit/timer (Phase 2), the Apps Script layer (Phase 5), and the
Discord Developer Portal setup (Phase 6) are typed by hand, not generated. See `.claude/CLAUDE.md`
for the full rule.
