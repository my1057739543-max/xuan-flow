"""Skill types definition."""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Skill:
    """Represents a skill with its metadata and file path."""
    name: str
    description: str
    license: str | None
    skill_dir: Path
    skill_file: Path
    relative_path: Path
    category: str  # 'public' or 'custom'
    enabled: bool = False

    @property
    def skill_path(self) -> str:
        """Returns the relative path from the category root."""
        path = self.relative_path.as_posix()
        return "" if path == "." else path

    def get_workspace_path(self, workspace_base_path: str = ".xuan-flow/skills") -> str:
        """Get the logical path to this skill in the workspace."""
        category_base = f"{workspace_base_path}/{self.category}"
        skill_path = self.skill_path
        if skill_path:
            return f"{category_base}/{skill_path}"
        return category_base

    def get_workspace_file_path(self, workspace_base_path: str = ".xuan-flow/skills") -> str:
        """Get the full logical path to this skill's SKILL.md file."""
        return f"{self.get_workspace_path(workspace_base_path)}/SKILL.md"
