"""Loader for scanning and loading Skills from directories."""

import os
from pathlib import Path

from xuan_flow.config.app_config import get_app_config
from xuan_flow.skills.parser import parse_skill_file
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
    config = get_app_config()
    # In xuan-flow, skills are always enabled for simplicity or read from config if we add it
    # For now, we just scan and assume all are enabled if they parse correctly
    
    skills_path = get_skills_root_path()
    
    if not skills_path.exists():
        return []

    skills = []

    # Scan public and custom directories
    for category in ["public", "custom"]:
        category_path = skills_path / category
        if not category_path.exists() or not category_path.is_dir():
            continue

        for current_root, dir_names, file_names in os.walk(category_path):
            dir_names[:] = sorted(name for name in dir_names if not name.startswith("."))
            if "SKILL.md" not in file_names:
                continue

            skill_file = Path(current_root) / "SKILL.md"
            relative_path = skill_file.parent.relative_to(category_path)

            skill = parse_skill_file(skill_file, category=category, relative_path=relative_path)
            if skill:
                # Default true for now in xuan-flow 
                skill.enabled = True
                skills.append(skill)

    # Sort by name for consistent ordering
    skills.sort(key=lambda s: s.name)

    return skills
