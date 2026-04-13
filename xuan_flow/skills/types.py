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
    skill_file: Path | None
    config_file: Path | None
    scripts_dir: Path | None
    entrypoint: str | None
    invocation_hint: str | None
    relative_path: Path
    category: str  # 'public' or 'custom'
    enabled: bool = False

    @property
    def skill_path(self) -> str:
        """Returns the relative path from the category root."""
        path = self.relative_path.as_posix()
        return "" if path == "." else path

    def get_workspace_path(self) -> str:
        """Get absolute directory path for this skill."""
        return str(self.skill_dir.resolve())

    def get_workspace_file_path(self) -> str:
        """Get the best readable skill file path for read_file tool."""
        if self.skill_file is not None:
            return str(self.skill_file.resolve())
        if self.config_file is not None:
            return str(self.config_file.resolve())
        return str(self.skill_dir.resolve())

    def get_entry_script_path(self) -> str | None:
        """Get absolute entry script path if this skill has executable scripts."""
        if self.scripts_dir is None or not self.entrypoint:
            return None
        return str((self.scripts_dir / self.entrypoint).resolve())
