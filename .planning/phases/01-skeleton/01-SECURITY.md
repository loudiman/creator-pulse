---
phase: 01
slug: skeleton
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: 2026-07-30
---

# Phase 01 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

Register origin: **authored at plan time** — all three PLAN.md files carried a `<threat_model>`
block, so this audit verifies stated mitigations rather than building a register retroactively.
ASVS level 1, `security_block_on: high`. Classification depth is grep-level, which is what L1
authorises; no deeper boundary-placement or end-to-end trace analysis was performed.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| PyPI → local venv | Third-party code from a public registry executes on the dev box and later the VPS | Executable package code |
| `creators.yaml` → `config.load_creators` | A file on disk is deserialized into live Python objects | Operator-authored config |
| venv `bin`/`Scripts` → shell PATH | An installed console script becomes an invokable command | Executable entry point |
| operator `--source`/`--case` → filesystem write path | Operator-shaped strings joined into a written path | Path segments |
| remote URL → local fixture file | Bytes from a public endpoint persisted into the repository | Untrusted response body |
| test suite → network | The suite must be provably unable to reach the network (OPS-04) | — (must not cross) |
| working tree → git history | Any file not matched by an ignore rule can be committed; an un-commit is a rotation, not a fix | Potentially secrets |
| gate result → phase closure | Every later phase is judged by four commands; a weakened gate reports green while meaning nothing | Verification verdict |
| README → operator | A stranger provisioning the VPS executes what this file says | Install instructions |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-01-SC | Tampering | `pip install -e ".[dev]"` — eight PyPI packages | high | mitigate | Blocking-human legitimacy gate discharged in `221cb6c` with a PyPI JSON-API audit of all eight. Verified: every dependency uses an exact `==` pin (`gspread==6.2.1`, `discord.py==2.7.1`, `playwright==1.61.0`, `PyYAML==6.0.3`, `requests==2.34.2`, `pytest==9.1.1`, `ruff==0.16.0`, `mypy==2.3.0`); the only loose specifier in the file is the build-system `setuptools>=68`. No ninth package present. | closed |
| T-01-01 | Tampering | `config.load_creators` deserializing `creators.yaml` | medium | mitigate | Verified `src/creatorpulse/config.py:22` uses `yaml.safe_load`; negative grep for unqualified `yaml.load(` over `src/` returns nothing. | closed |
| T-01-02 | Information disclosure | `pyproject.toml` committed to a public repo | low | accept | Verified: no secret/token/password/api-key string in the file. Metadata and pins only. See Accepted Risks. | closed |
| T-01-03 | Elevation of privilege | `creatorpulse` console script placed on PATH | low | accept | Verified `[project.scripts]` declares a single user-scope entry point (`creatorpulse = "creatorpulse.cli:main"`); installed into a user-owned venv, not system-wide, not setuid. See Accepted Risks. | closed |
| T-01-04 | Tampering | `scripts/record_fixture.py` path composition from `--source` and `--case` | medium | mitigate | Verified both segments are checked against `^[a-z0-9_]+$` (line 31) before any connection opens, and a resolved-path containment guard (`if FIXTURES_ROOT not in target.parents`, line 36) rejects any write outside the fixtures root. Residual observations below — neither defeats the control. | closed |
| T-01-05 | Information disclosure | A recorded fixture body committed into a public repository | medium | mitigate | **Mitigation partially absent.** Verified there is no authenticated request path in Phase 1 — the recorder sends no `headers=`, `auth=`, cookie, or bearer token, so no credential can appear in a recorded body. **However**, the register's second claim is not satisfied: `tests/fixtures/README.md` does *not* record that fixtures are reviewed before commit. It documents the layout and the hand-run rule only. | **open — below `high` threshold (non-blocking)** |
| T-01-06 | Spoofing | A non-2xx or interstitial response saved as if it were a real fixture | medium | mitigate | Verified `response.raise_for_status()` (line 41) runs before any write, so a 403 or challenge page cannot be persisted as a fixture. | closed |
| T-01-07 | Denial of service | An unbounded fetch hanging the operator's shell | low | mitigate | Verified explicit `timeout=_TIMEOUT_SECONDS` (30s) on the request (line 40). Script is hand-run and single-shot. | closed |
| T-01-08 | Repudiation | A live network call sneaking into the pytest suite | low | mitigate | Verified `testpaths = ["tests"]` in `pyproject.toml:49`; the recorder lives in `scripts/`. Only imports under `tests/` are `pathlib.Path` and `creatorpulse.config` — no `requests`, `urllib`, `httpx`, `socket`, `playwright`, or `record_fixture` reference in any test module. | closed |
| T-01-09 | Information disclosure | A secret path reaching git history via a missing ignore rule | high | mitigate | Verified behaviourally against git itself, not against `.gitignore` text: `git check-ignore -q` exits 0 for `.env`, `creatorpulse.db`, `.venv`, and `.planning/research/.cache`. `git status --porcelain` reports 0 lines on a tree that has had a full install and gate run. Independently re-confirmed in a fresh clone during UAT. | closed |
| T-01-10 | Repudiation | A weakened gate reporting green | medium | mitigate | Verified negative grep for `# noqa` / `# type: ignore` across `src/` returns nothing; no ruff rule was removed from the selection and no path was excluded from ruff's scope. The one formatting finding surfaced during the phase (`ARCHITECTURE.md`) was fixed with `ruff format .`, not by exclusion. | closed |
| T-01-11 | Tampering | An overwrite of the already-committed `.gitignore` | medium | mitigate | Verified `git diff 221cb6c..HEAD -- .gitignore` shows **0** deletion lines — append-only, no block rewritten or reordered. | closed |
| T-01-12 | Spoofing | A README install step that silently selects the wrong interpreter | low | mitigate | Verified `requires-python = ">=3.12,<3.13"` bounds the interpreter so a mismatched venv fails at install; README pins `py -3.12` (Windows) and `python3.12` (Linux) explicitly and explains why bare `python`/`py` are wrong. Exercised end-to-end in the fresh-clone UAT. | closed |

*Status: open · closed · open — below `high` threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above `workflow.security_block_on` (`high`) count toward `threats_open`*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

**`threats_open: 0`** — the one open threat (T-01-05) is `medium`, below the `high` block threshold, so it does not gate phase advancement. It is real and should be closed; see Open Items.

---

## Open Items

### T-01-05 — fixture review step undocumented

The register promised two controls. One is present (no auth path exists, so no credential can land
in a fixture body). The other is not: nothing tells the operator to read a fixture before committing
it. Since fixtures are raw third-party response bodies persisted into a public repository, "look at
it first" is the only control standing between a surprising response body and git history — and an
un-commit is a rotation, not a fix.

**Fix:** one line in `tests/fixtures/README.md` stating that fixture bodies are reviewed before
commit. Not applied here — this audit records findings and does not edit implementation files.

### Residual observations on T-01-04 (not threats, noted for the record)

Neither defeats the containment guard; both are hardening, not gaps:

1. `--ext` is not validated by `_NAME_RE` — only `--source` and `--case` are. A traversal attempt via
   `--ext` is still caught by the resolved-path containment guard, but `--ext` does control the final
   filename suffix. Combined with a `case` of `test_something`, an operator could write a collectable
   `.py` file under `tests/fixtures/`. The input is operator-supplied on a single-operator machine, so
   this is a footgun rather than an attack surface.
2. `_NAME_RE.match` with a `$`-anchored pattern accepts a trailing newline (Python `$` matches before
   a final `\n`). `fullmatch` would be strictly tighter. No traversal is possible either way, since the
   character class admits no separator or dot.

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-01-01 | T-01-02 | `pyproject.toml` holds package metadata and version pins only. Secrets load from a `chmod 600` env file via systemd `EnvironmentFile` in Phase 2 (OPS-01) and never enter the repo. | author (plan-time disposition) | 2026-07-30 |
| R-01-02 | T-01-03 | Single-operator machine. The venv directory is user-owned; the console script is not installed system-wide and is not setuid. | author (plan-time disposition) | 2026-07-30 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-30 | 13 | 12 | 1 (medium, non-blocking) | agent (orchestrator, ASVS L1 grep-depth) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed — no open threat at or above the `high` block threshold
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-30 — with T-01-05 recorded as an open non-blocking item.
