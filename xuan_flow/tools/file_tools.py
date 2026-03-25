"""File manipulation tools for the Agent's Workspace."""

import logging
import os
from pathlib import Path

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# Define the directories relative to the project root
WORKSPACE_DIR = (Path.cwd() / ".xuan-flow" / "workspace").resolve()
SKILLS_DIR = (Path.cwd() / "skills").resolve()

def _get_safe_path(filename: str, allow_skills: bool = True) -> Path | None:
    """Ensure the filename resolves to a path inside the workspace or skills dir."""
    try:
        # Create workspace dir if it doesn't exist
        WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
        
        # Candidate paths
        path_obj = Path(filename)
        
        # If absolute, check if it starts with one of our roots
        if path_obj.is_absolute():
            resolved_path = path_obj.resolve()
        else:
            # Try workspace first
            resolved_path = (WORKSPACE_DIR / path_obj).resolve()
            if not str(resolved_path).startswith(str(WORKSPACE_DIR)) and allow_skills:
                # Try skills root
                resolved_path = (SKILLS_DIR / path_obj).resolve()

        # Final safety check: must be inside WORKSPACE_DIR OR SKILLS_DIR
        is_in_workspace = str(resolved_path).startswith(str(WORKSPACE_DIR))
        is_in_skills = allow_skills and str(resolved_path).startswith(str(SKILLS_DIR))
        
        if not (is_in_workspace or is_in_skills):
            logger.warning(f"Access denied to path: {resolved_path}")
            return None
            
        return resolved_path
    except Exception as e:
        logger.error(f"Path resolution error: {e}")
        return None


@tool
def write_file(filename: str, content: str) -> str:
    """Write text content to a file in the workspace.
    
    Use this to save reports, code, or generate readable documents for the user.
    If the user asks for a PDF, generate the content as Markdown (.md) first,
    and explain that you've saved the Markdown version to the workspace.

    Args:
        filename: The name of the file to create (e.g., 'report.md', 'script.py').
        content: The text content to write to the file.

    Returns:
        A success message with the file path, or an error message.
    """
    safe_path = _get_safe_path(filename, allow_skills=False)
    if not safe_path:
        return f"Error: Invalid filename '{filename}'."

    try:
        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote {len(content)} characters to {safe_path}"
    except Exception as e:
        return f"Failed to write file: {e}"


@tool
def read_file(filename: str) -> str:
    """Read text content from a file in the workspace or skills directory.

    Args:
        filename: The name or path of the file to read.

    Returns:
        The content of the file, or an error message.
    """
    safe_path = _get_safe_path(filename, allow_skills=True)
    if not safe_path:
        return f"Error: Invalid filename or access denied: '{filename}'."

    if not safe_path.exists() or not safe_path.is_file():
        return f"Error: File '{filename}' does not exist."

    try:
        with open(safe_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Failed to read file: {e}"


@tool
def delete_file(filename: str) -> str:
    """Delete a file from the workspace.

    Args:
        filename: The name of the file to delete.

    Returns:
        A success message or an error message if the file doesn't exist or deletion fails.
    """
    safe_path = _get_safe_path(filename, allow_skills=False)
    if not safe_path:
        return f"Error: Invalid filename '{filename}'."

    if not safe_path.exists() or not safe_path.is_file():
        return f"Error: File '{filename}' does not exist in the workspace."

    try:
        safe_path.unlink()
        return f"Successfully deleted {safe_path.name} from workspace."
    except Exception as e:
        return f"Failed to delete file: {e}"
