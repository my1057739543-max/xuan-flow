"""YAML frontmatter parser for SKILL.md files."""

import logging
from pathlib import Path

import yaml

from xuan_flow.skills.types import Skill

logger = logging.getLogger(__name__)


def parse_skill_file(skill_file: Path, category: str, relative_path: Path) -> Skill | None:
    """Parse a SKILL.md file and extract metadata from YAML frontmatter.

    Args:
        skill_file: Path to the SKILL.md file
        category: 'public' or 'custom'
        relative_path: Relative path from category root to the skill directory

    Returns:
        Skill object if successfully parsed, None otherwise.
    """
    try:
        if not skill_file.exists():
            return None

        content = skill_file.read_text(encoding="utf-8")

        # Parse frontmatter (--- ... ---)
        if not content.startswith("---"):
            logger.warning("No YAML frontmatter found in %s", skill_file)
            return None

        end_idx = content.find("\n---\n")
        if end_idx == -1:
            end_idx = content.find("\n---")
            if end_idx == -1:
                logger.warning("Unterminated YAML frontmatter in %s", skill_file)
                return None

        frontmatter_text = content[3:end_idx].strip()
        try:
            metadata = yaml.safe_load(frontmatter_text) or {}
        except yaml.YAMLError as e:
            logger.warning("Invalid YAML frontmatter in %s: %e", skill_file, e)
            return None

        name = metadata.get("name")
        description = metadata.get("description")

        if not name or not description:
            logger.warning("Missing required fields (name, description) in %s", skill_file)
            return None

        return Skill(
            name=str(name),
            description=str(description),
            license=metadata.get("license"),
            skill_dir=skill_file.parent,
            skill_file=skill_file,
            relative_path=relative_path,
            category=category,
        )

    except Exception as e:
        logger.error("Failed to parse skill file %s: %e", skill_file, e)
        return None
