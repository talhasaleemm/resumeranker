"""
app/services/normalization/normalizer.py — Skill Normalization
Normalizes raw skills extracted via NER into canonical terms using skill_taxonomy.json.
"""
import json
import os
import re
from typing import Dict, List, Set

# Load taxonomy singleton
_TAXONOMY_PATH = os.path.join(os.path.dirname(__file__), "skill_taxonomy.json")
_ALIAS_MAP: Dict[str, str] = {}

if os.path.exists(_TAXONOMY_PATH):
    with open(_TAXONOMY_PATH, "r", encoding="utf-8") as f:
        _taxonomy: Dict[str, List[str]] = json.load(f)
        for canonical, aliases in _taxonomy.items():
            for alias in aliases:
                _ALIAS_MAP[alias.lower()] = canonical
else:
    _ALIAS_MAP = {}


def _clean_string(s: str) -> str:
    """Lowercase and remove excess whitespace/punctuation."""
    s = s.lower().strip()
    # Remove trailing punctuation often caught by NER
    s = re.sub(r"[.,;:]+$", "", s)
    return s


def normalize_skill(skill: str) -> str:
    """
    Returns the canonical version of a skill if found in taxonomy.
    Otherwise, returns the cleaned original skill.
    """
    cleaned = _clean_string(skill)
    return _ALIAS_MAP.get(cleaned, cleaned)


def normalize_skills_list(skills: List[str]) -> List[str]:
    """
    Normalizes a list of skills and deduplicates them.
    """
    normalized_set: Set[str] = set()
    for s in skills:
        if not s.strip():
            continue
        normalized_set.add(normalize_skill(s))
    return sorted(list(normalized_set))
