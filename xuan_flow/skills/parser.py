"""YAML frontmatter parser for SKILL.md files."""

import logging
from pathlib import Path

import yaml

from xuan_flow.skills.types import Skill

logger = logging.getLogger(__name__)


def parse_skill_dir(skill_dir: Path, category: str, relative_path: Path) -> Skill | None:
    """Parse a directory-based skill that contains config.yaml and scripts/.

    Expected structure:
    - <skill_dir>/config.yaml
    - <skill_dir>/scripts/<entrypoint>
    - optional <skill_dir>/SKILL.md for human-readable workflow guidance
    """
    try:
        config_file = skill_dir / "config.yaml"
        if not config_file.exists():
            return None

        raw = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            logger.warning("Invalid config format in %s", config_file)
            return None

        name = raw.get("name")
        description = raw.get("description")
        entrypoint = raw.get("entrypoint")

        if not name or not description or not entrypoint:
            logger.warning("Missing required fields (name, description, entrypoint) in %s", config_file)
            return None

        scripts_dir = skill_dir / "scripts"
        script_path = (scripts_dir / str(entrypoint)).resolve()
        if not scripts_dir.exists() or not scripts_dir.is_dir():
            logger.warning("Missing scripts directory for %s", config_file)
            return None
        if scripts_dir.resolve() not in script_path.parents or not script_path.exists():
            logger.warning("Invalid or missing entrypoint '%s' in %s", entrypoint, config_file)
            return None

        skill_doc = skill_dir / "SKILL.md"

        enabled = bool(raw.get("enabled", True))

        return Skill(
            name=str(name),
            description=str(description),
            license=raw.get("license"),
            skill_dir=skill_dir,
            skill_file=skill_doc if skill_doc.exists() else None,
            config_file=config_file,
            scripts_dir=scripts_dir,
            entrypoint=str(entrypoint),
            invocation_hint=(str(raw.get("invocation_hint")) if raw.get("invocation_hint") else None),
            relative_path=relative_path,
            category=category,
            enabled=enabled,
        )
    except Exception as e:
        logger.error("Failed to parse skill directory %s: %s", skill_dir, e)
        return None


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
            logger.warning("Invalid YAML frontmatter in %s: %s", skill_file, e)
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
            config_file=None,
            scripts_dir=None,
            entrypoint=None,
            invocation_hint=None,
            relative_path=relative_path,
            category=category,
            enabled=True,
        )

    except Exception as e:
        logger.error("Failed to parse skill file %s: %s", skill_file, e)
        return None
