"""Dictionary-based skill extraction from job descriptions and tags."""
from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources

# Tokens like "C++", "C#", "node.js" mean we can't use \b; instead require that the
# alias is not glued to other identifier characters on either side.
_LEFT = r"(?<![A-Za-z0-9_+#.])"
_RIGHT = r"(?![A-Za-z0-9_+#])"


@dataclass(frozen=True)
class Skill:
    name: str
    category: str
    patterns: tuple[re.Pattern, ...]
    tag_aliases: frozenset[str]


def _compile_alias(alias: str) -> re.Pattern | None:
    if alias.startswith("re:"):
        return re.compile(alias[3:])
    if alias.startswith("="):
        return re.compile(_LEFT + re.escape(alias[1:]) + _RIGHT)
    if alias.startswith("#"):
        return None
    return re.compile(_LEFT + re.escape(alias) + _RIGHT, re.IGNORECASE)


@lru_cache(maxsize=1)
def load_taxonomy() -> tuple[Skill, ...]:
    raw = json.loads(resources.files("sajobs").joinpath("skills_taxonomy.json").read_text(encoding="utf-8"))
    skills = []
    for category, entries in raw["categories"].items():
        for name, aliases in entries.items():
            aliases = [str(a) for a in aliases]
            patterns = tuple(p for p in (_compile_alias(a) for a in aliases) if p is not None)
            tag_aliases = {name.lower()}
            for alias in aliases:
                if alias.startswith("re:"):
                    continue
                tag_aliases.add(alias.lstrip("=#").lower())
            skills.append(Skill(name, category, patterns, frozenset(tag_aliases)))
    return tuple(skills)


@lru_cache(maxsize=1)
def skill_categories() -> dict[str, str]:
    return {skill.name: skill.category for skill in load_taxonomy()}


@lru_cache(maxsize=1)
def _canonical_names() -> dict[str, str]:
    return {skill.name.lower(): skill.name for skill in load_taxonomy()}


def canonical_skill(name: str | None) -> str | None:
    """Return the taxonomy spelling of ``name`` (case-insensitive), or ``None`` if unknown."""
    if not isinstance(name, str):
        return None
    return _canonical_names().get(name.strip().lower())


def skill_list() -> list[dict[str, str]]:
    """Every known skill as ``[{"name": ..., "category": ...}]`` sorted by name."""
    return sorted(
        ({"name": s.name, "category": s.category} for s in load_taxonomy()), key=lambda s: s["name"].lower()
    )


def extract_skills(text: str | None, tags: Iterable[str] | None = None) -> list[dict[str, str]]:
    """Return ``[{"skill": ..., "category": ...}]`` found in the text or tags, sorted by name."""
    text = text or ""
    normalized_tags = {t.strip().lower() for t in (tags or []) if t and t.strip()}
    found = []
    for skill in load_taxonomy():
        if normalized_tags & skill.tag_aliases or any(p.search(text) for p in skill.patterns):
            found.append({"skill": skill.name, "category": skill.category})
    return sorted(found, key=lambda s: s["skill"].lower())


def extract_skill_names(text: str | None, tags: Iterable[str] | None = None) -> list[str]:
    return [s["skill"] for s in extract_skills(text, tags)]
