"""Parse-only reader for creators.yaml, plus env/default path resolution.

No validation — see Phase 3 CFG-03.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path("creators.yaml")
DEFAULT_DB_PATH = Path("creatorpulse.db")


@dataclass(frozen=True, slots=True)
class Creator:
    id: str
    name: str
    sources: dict[str, str]


def resolve_paths() -> tuple[Path, Path]:
    """Resolve config and db paths from the environment, falling back to repo-relative defaults."""
    config_env: str | None = os.environ.get("CREATORPULSE_CONFIG")
    db_env: str | None = os.environ.get("CREATORPULSE_DB")
    config_path = Path(config_env) if config_env else DEFAULT_CONFIG_PATH
    db_path = Path(db_env) if db_env else DEFAULT_DB_PATH
    return config_path.resolve(), db_path.resolve()


def load_creators(path: Path = DEFAULT_CONFIG_PATH) -> list[Creator]:
    """Read and parse creators.yaml into a list of Creator objects. Parse-only, no validation."""
    text = path.read_text(encoding="utf-8")
    data: dict[str, Any] = yaml.safe_load(text)
    entries: list[dict[str, Any]] = data["creators"]
    return [
        Creator(
            id=str(entry["id"]),
            name=str(entry["name"]),
            sources=dict(entry["sources"]),
        )
        for entry in entries
    ]
