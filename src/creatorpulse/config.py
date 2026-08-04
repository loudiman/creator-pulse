"""Read, validate, and parse creators.yaml, plus env/default path resolution.

validate() walks the whole file and gathers every problem before any network call (CFG-03).
load_creators() stays parse-only and its signature is unchanged.
"""

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from creatorpulse import sources as source_registry

DEFAULT_CONFIG_PATH = Path("creators.yaml")
DEFAULT_DB_PATH = Path("creatorpulse.db")

_SLUG_RE = re.compile(r"^[a-z0-9-]+$")


@dataclass(frozen=True, slots=True)
class Creator:
    id: str
    name: str
    sources: dict[str, str]


class ValidationError(Exception):
    """Raised by validate() carrying every problem it gathered, in file order (D-11)."""

    problems: tuple[str, ...]

    def __init__(self, problems: list[str]) -> None:
        self.problems = tuple(problems)
        super().__init__(f"{len(self.problems)} problem(s) in creators.yaml")


def resolve_paths() -> tuple[Path, Path]:
    """Resolve config and db paths from the environment, falling back to repo-relative defaults."""
    config_env: str | None = os.environ.get("CREATORPULSE_CONFIG")
    db_env: str | None = os.environ.get("CREATORPULSE_DB")
    config_path = Path(config_env) if config_env else DEFAULT_CONFIG_PATH
    db_path = Path(db_env) if db_env else DEFAULT_DB_PATH
    return config_path.resolve(), db_path.resolve()


def load_raw(path: Path) -> dict[str, Any]:
    """Read creators.yaml as UTF-8 and parse it into a dict. Nothing is checked yet."""
    text = path.read_text(encoding="utf-8")
    data: dict[str, Any] = yaml.safe_load(text)
    return data


def validate(raw: dict[str, Any]) -> None:
    """Gather every D-12 problem in a parsed creators.yaml structure; raise if any exist."""
    problems: list[str] = []
    creators = raw.get("creators")
    if not isinstance(creators, list) or not creators:
        problems.append("creator=<missing> field=creators: missing or not a non-empty list")
        raise ValidationError(problems)

    seen_ids: set[str] = set()
    for entry in creators:
        cid = str(entry.get("id") or "").strip()
        name = str(entry.get("name") or "").strip()
        entry_sources = entry.get("sources")
        label = cid or "<missing>"

        if not cid or not _SLUG_RE.match(cid):
            problems.append(f"creator={label} field=id: missing or not a lowercase ASCII slug")
        elif cid in seen_ids:
            problems.append(f"creator={cid} field=id: duplicate id, already used by another entry")
        else:
            seen_ids.add(cid)

        if not name:
            problems.append(f"creator={label} field=name: missing or blank")

        if not isinstance(entry_sources, dict) or not entry_sources:
            problems.append(f"creator={label} field=sources: missing or not a non-empty map")
        else:
            for platform, identifier in entry_sources.items():
                if platform not in source_registry.KNOWN_PLATFORMS:
                    problems.append(f"creator={label} field=sources.{platform}: unknown platform")
                if not str(identifier).strip():
                    problems.append(f"creator={label} field=sources.{platform}: empty identifier")

    if problems:
        raise ValidationError(problems)


def load_creators(path: Path = DEFAULT_CONFIG_PATH) -> list[Creator]:
    """Read and parse creators.yaml into a list of Creator objects. Parse-only, no validation."""
    data = load_raw(path)
    entries: list[dict[str, Any]] = data["creators"]
    return [
        Creator(
            id=str(entry["id"]),
            name=str(entry["name"]),
            sources=dict(entry["sources"]),
        )
        for entry in entries
    ]
