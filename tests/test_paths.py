"""Tests for resolve_paths() and its threading into run_collect().

Fixtures only, no live network calls. Runs on Windows with no systemd present —
assertions target resolve_paths()'s behavior given environment state, never the
OS mechanism (systemd) that would set that state on a real box.
"""

from pathlib import Path

import pytest

from creatorpulse.cli import run_collect
from creatorpulse.config import DEFAULT_CONFIG_PATH, DEFAULT_DB_PATH, resolve_paths

CREATORS_YAML = "creators:\n  - id: xqc\n    name: xQc\n    sources:\n      youtube: '@xQcOW'\n"


def test_resolve_paths_uses_env_vars_when_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CREATORPULSE_CONFIG", str(tmp_path / "creators.yaml"))
    monkeypatch.setenv("CREATORPULSE_DB", str(tmp_path / "creatorpulse.db"))

    config_path, db_path = resolve_paths()

    assert config_path == (tmp_path / "creators.yaml").resolve()
    assert db_path == (tmp_path / "creatorpulse.db").resolve()


def test_resolve_paths_falls_back_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CREATORPULSE_CONFIG", raising=False)
    monkeypatch.delenv("CREATORPULSE_DB", raising=False)

    config_path, db_path = resolve_paths()

    assert config_path == DEFAULT_CONFIG_PATH.resolve()
    assert db_path == DEFAULT_DB_PATH.resolve()


def test_resolve_paths_mixed_case_falls_back_independently(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CREATORPULSE_CONFIG", str(tmp_path / "creators.yaml"))
    monkeypatch.delenv("CREATORPULSE_DB", raising=False)

    config_path, db_path = resolve_paths()

    assert config_path == (tmp_path / "creators.yaml").resolve()
    assert db_path == DEFAULT_DB_PATH.resolve()


def test_resolve_paths_empty_string_treated_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CREATORPULSE_DB", "")
    monkeypatch.delenv("CREATORPULSE_CONFIG", raising=False)

    config_path, db_path = resolve_paths()

    assert db_path == DEFAULT_DB_PATH.resolve()


def test_run_collect_logs_both_resolved_paths(
    caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    config_path = tmp_path / "creators.yaml"
    config_path.write_text(CREATORS_YAML, encoding="utf-8")
    db_path = tmp_path / "creatorpulse.db"

    with caplog.at_level("INFO", logger="creatorpulse"):
        run_collect(config_path, db_path)

    run_start_records = [r for r in caplog.records if str(config_path) in r.getMessage()]
    assert run_start_records
    assert any(str(db_path) in r.getMessage() for r in run_start_records)
