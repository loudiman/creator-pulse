"""Tests for creatorpulse.config — parse-level coverage over the committed creators.yaml.

Fixtures only, no live network calls. Asserts on parsed Creator objects, not raw YAML text.
"""

from pathlib import Path

from creatorpulse.config import Creator, load_creators

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
