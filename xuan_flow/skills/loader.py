"""Loader for scanning and loading Skills from directories."""

import os
from pathlib import Path

from xuan_flow.skills.parser import parse_skill_dir, parse_skill_file
from xuan_flow.skills.types import Skill


def get_skills_root_path() -> Path:
    """Get the default root path for skills."""
    # Assuming xuan-langgragh/skills
    return Path.cwd() / "skills"


def load_skills(enabled_only: bool = False) -> list[Skill]:
    """Scan and load all skills from the skills directory.

    Args:
        enabled_only: If True, only return enabled skills.

    Returns:
        List of Skill objects, sorted by name.
    """
    skills_path = get_skills_root_path()
    
    if not skills_path.exists():
        return []

    discovered: dict[str, Skill] = {}

    # Scan public and custom directories
    for category in ["public", "custom"]:
        category_path = skills_path / category
        if not category_path.exists() or not category_path.is_dir():
            continue

        for current_root, dir_names, file_names in os.walk(category_path):
            dir_names[:] = sorted(name for name in dir_names if not name.startswith("."))
            current_dir = Path(current_root)
            relative_path = current_dir.relative_to(category_path)

            skill: Skill | None = None

            # New format first: directory with config.yaml + scripts/
            if "config.yaml" in file_names:
                skill = parse_skill_dir(current_dir, category=category, relative_path=relative_path)
            elif "SKILL.md" in file_names:
                # Legacy format compatibility
                skill_file = current_dir / "SKILL.md"
                skill = parse_skill_file(skill_file, category=category, relative_path=relative_path)

            if skill is None:
                continue

            # Conflict policy: custom skill overrides public skill with same name
            previous = discovered.get(skill.name)
            if previous is not None:
                if previous.category == "public" and skill.category == "custom":
                    discovered[skill.name] = skill
                else:
                    # Keep the first one in all other cases for deterministic behavior
                    continue
            else:
                discovered[skill.name] = skill

    # Sort by name for consistent ordering
    skills = sorted(discovered.values(), key=lambda s: s.name)

    if enabled_only:
        skills = [s for s in skills if s.enabled]

    return skills


def get_skill_by_name(name: str, enabled_only: bool = True) -> Skill | None:
    """Get a skill by name (case-insensitive exact match)."""
    target = name.strip().lower()
    for skill in load_skills(enabled_only=enabled_only):
        if skill.name.lower() == target:
            return skill
    return None
