"""Tests for creatorpulse.config — parse-level coverage over the committed creators.yaml,
plus validate()'s D-12 rule set (CFG-02, CFG-03).

Fixtures only, no live network calls. Asserts on parsed Creator objects, not raw YAML text.
"""

import sqlite3
from pathlib import Path
from typing import Any

import pytest
from test_collector import _fake_response

from creatorpulse.cli import run_collect
from creatorpulse.config import Creator, ValidationError, load_creators, load_raw, validate

CREATORS_YAML = Path(__file__).resolve().parent.parent / "creators.yaml"


def test_committed_creators_yaml_loads() -> None:
    creators = load_creators(CREATORS_YAML)

    assert len(creators) > 0
    assert all(isinstance(creator, Creator) for creator in creators)

    for creator in creators:
        assert creator.id
        assert creator.name
        assert creator.sources
        assert all(isinstance(value, str) and value for value in creator.sources.values())

    ids = [creator.id for creator in creators]
    assert len(ids) == len(set(ids))


def test_committed_creators_yaml_validates_clean() -> None:
    raw = load_raw(CREATORS_YAML)

    validate(raw)  # must not raise — three creators, nine source keys, tiktok included

    assert len(load_creators(CREATORS_YAML)) == 3


def _base_entry(**overrides: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "id": "a-creator",
        "name": "A Creator",
        "sources": {"youtube": "@handle"},
    }
    entry.update(overrides)
    return entry


def test_missing_creators_key_raises_one_problem() -> None:
    with pytest.raises(ValidationError) as exc_info:
        validate({})

    assert len(exc_info.value.problems) == 1
    assert "creators" in exc_info.value.problems[0]


def test_empty_creators_list_raises_one_problem() -> None:
    with pytest.raises(ValidationError) as exc_info:
        validate({"creators": []})

    assert len(exc_info.value.problems) == 1


def test_non_list_creators_raises_one_problem() -> None:
    with pytest.raises(ValidationError) as exc_info:
        validate({"creators": "not-a-list"})

    assert len(exc_info.value.problems) == 1


def test_missing_id_produces_problem_naming_id() -> None:
    entry = _base_entry()
    del entry["id"]

    with pytest.raises(ValidationError) as exc_info:
        validate({"creators": [entry]})

    assert any("field=id" in p for p in exc_info.value.problems)


def test_invalid_id_slug_produces_problem_naming_id() -> None:
    entry = _base_entry(id="Not A Slug!")

    with pytest.raises(ValidationError) as exc_info:
        validate({"creators": [entry]})

    assert any("field=id" in p for p in exc_info.value.problems)


def test_duplicate_id_flags_second_entry_only() -> None:
    first = _base_entry(id="dup", name="First")
    second = _base_entry(id="dup", name="Second")

    with pytest.raises(ValidationError) as exc_info:
        validate({"creators": [first, second]})

    id_problems = [p for p in exc_info.value.problems if "field=id" in p]
    assert len(id_problems) == 1
    assert "duplicate" in id_problems[0]


def test_missing_name_produces_problem_naming_name() -> None:
    entry = _base_entry()
    del entry["name"]

    with pytest.raises(ValidationError) as exc_info:
        validate({"creators": [entry]})

    assert any("field=name" in p for p in exc_info.value.problems)


def test_whitespace_only_name_produces_problem_naming_name() -> None:
    entry = _base_entry(name="   ")

    with pytest.raises(ValidationError) as exc_info:
        validate({"creators": [entry]})

    assert any("field=name" in p for p in exc_info.value.problems)


def test_missing_sources_produces_problem_naming_sources() -> None:
    entry = _base_entry()
    del entry["sources"]

    with pytest.raises(ValidationError) as exc_info:
        validate({"creators": [entry]})

    assert any("field=sources" in p for p in exc_info.value.problems)


def test_empty_sources_map_produces_problem_naming_sources() -> None:
    entry = _base_entry(sources={})

    with pytest.raises(ValidationError) as exc_info:
        validate({"creators": [entry]})

    assert any("field=sources" in p for p in exc_info.value.problems)


def test_unknown_platform_key_fails_validation() -> None:
    entry = _base_entry(sources={"youtub": "@handle"})

    with pytest.raises(ValidationError) as exc_info:
        validate({"creators": [entry]})

    assert any("sources.youtub" in p for p in exc_info.value.problems)


def test_known_unregistered_platform_tiktok_does_not_fail() -> None:
    entry = _base_entry(sources={"youtube": "@handle", "tiktok": "@handle"})

    validate({"creators": [entry]})  # must not raise — known, merely unregistered


def test_empty_source_value_produces_problem() -> None:
    entry = _base_entry(sources={"youtube": "   "})

    with pytest.raises(ValidationError) as exc_info:
        validate({"creators": [entry]})

    assert any("sources.youtube" in p for p in exc_info.value.problems)


def test_validate_reports_every_problem() -> None:
    creators = [
        _base_entry(id="", name="Only Bad Id"),
        _base_entry(id="ok-two", name=""),
        _base_entry(id="ok-three", sources={}),
    ]

    with pytest.raises(ValidationError) as exc_info:
        validate({"creators": creators})

    assert len(exc_info.value.problems) == 3
    assert "field=id" in exc_info.value.problems[0]
    assert "field=name" in exc_info.value.problems[1]
    assert "field=sources" in exc_info.value.problems[2]


def test_validation_error_problems_is_tuple_of_strings() -> None:
    with pytest.raises(ValidationError) as exc_info:
        validate({})

    assert isinstance(exc_info.value.problems, tuple)
    assert all(isinstance(p, str) for p in exc_info.value.problems)


def test_load_raw_then_validate_on_malformed_tmp_path_file(tmp_path: Path) -> None:
    bad_yaml = tmp_path / "creators.yaml"
    bad_yaml.write_text(
        "creators:\n"
        "  - id: dup\n"
        "    name: A\n"
        "    sources:\n"
        "      youtube: '@a'\n"
        "  - id: dup\n"
        "    name: B\n"
        "    sources:\n"
        "      youtube: '@b'\n",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError) as exc_info:
        validate(load_raw(bad_yaml))

    assert any("field=id" in p and "duplicate" in p for p in exc_info.value.problems)


def test_run_collect_exit_code_2_on_validation_failure(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    bad_yaml = tmp_path / "creators.yaml"
    bad_yaml.write_text(
        "creators:\n"
        "  - id: dup\n"
        "    name: A\n"
        "    sources:\n"
        "      youtube: '@a'\n"
        "  - id: dup\n"
        "    name: B\n"
        "    sources:\n"
        "      youtub: '@b'\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "x.db"

    with caplog.at_level("ERROR", logger="creatorpulse"):
        exit_code = run_collect(bad_yaml, db_path)

    assert exit_code == 2
    problem_lines = [r.getMessage() for r in caplog.records if "field=" in r.getMessage()]
    assert problem_lines
    assert not db_path.exists()


def test_run_collect_fourth_creator_needs_no_code_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("YOUTUBE_API_KEY", "fake-key-for-test")
    fixture = Path(__file__).resolve().parent / "fixtures" / "youtube" / "channel_ok.json"
    ok_response = _fake_response(fixture)
    monkeypatch.setattr("creatorpulse.sources.youtube.requests.get", lambda *a, **kw: ok_response)

    base_text = CREATORS_YAML.read_text(encoding="utf-8")
    extra_entry = (
        "  - id: fourth-creator\n    name: Fourth Creator\n    sources:\n      youtube: '@fourth'\n"
    )
    config_path = tmp_path / "creators.yaml"
    config_path.write_text(base_text + extra_entry, encoding="utf-8")
    db_path = tmp_path / "creatorpulse.db"

    exit_code = run_collect(config_path, db_path)
    assert exit_code == 0

    conn = sqlite3.connect(db_path)
    count = conn.execute(
        "SELECT COUNT(*) FROM metrics WHERE creator_id = ?", ("fourth-creator",)
    ).fetchone()[0]
    conn.close()
    assert count == 1


def test_run_collect_returns_zero_when_a_source_failed_but_the_run_completed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A completed run exits 0 even with per-pair failures; the runs row carries the count.

    RUN-01 requires one failing source not to abort the run. Reporting such a run as a
    process failure would contradict that, and would leave the systemd unit permanently
    `failed` once any single creator hiccups. Non-zero is reserved for a run that did not
    complete: config missing (1), validation failed (2), or a crash that re-raises (D-16).
    """
    monkeypatch.setenv("YOUTUBE_API_KEY", "fake-key-for-test")

    def _boom(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("simulated transport failure")

    monkeypatch.setattr("creatorpulse.sources.youtube.requests.get", _boom)

    config_path = tmp_path / "creators.yaml"
    config_path.write_text(CREATORS_YAML.read_text(encoding="utf-8"), encoding="utf-8")
    db_path = tmp_path / "creatorpulse.db"

    exit_code = run_collect(config_path, db_path)

    assert exit_code == 0, "a completed run must not report itself as a process failure"

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT rows_written, failure_count FROM runs").fetchone()
    conn.close()

    assert row["failure_count"] > 0, "the failure must still be counted in the runs row"
    assert row["rows_written"] == 0, "every fetch failed, so no metric row was written"
