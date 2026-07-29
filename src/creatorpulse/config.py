"""Parse-only reader for creators.yaml. No validation — see Phase 3 CFG-03."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path("creators.yaml")


@dataclass(frozen=True, slots=True)
class Creator:
    id: str
    name: str
    sources: dict[str, str]


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
