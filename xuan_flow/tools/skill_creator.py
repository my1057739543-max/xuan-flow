import os
import yaml
from pathlib import Path
from langchain_core.tools import tool

@tool("create_skill_workflow", parse_docstring=True)
def create_skill_workflow(
    skill_name: str,
    description: str,
    instructions: str,
) -> str:
    """Create a new autonomous skill workflow for Xuan-Flow.

    Use this tool to permanently enhance Xuan-Flow's capabilities by writing a dynamic system prompt extension.
    This replaces the 'setup_agent' functionality from deer-flow, mapped to Xuan-Flow's unified Skill Engine.

    Args:
        skill_name: The internal identifier for the skill (e.g., 'code_reviewer', 'frontend_expert').
        description: A short high-level summary of what this skill enables the agent to do.
        instructions: The detailed markdown instructions, rules, and procedures the agent should follow when this skill is equipped.
    """
    try:
        # Resolve skills directory relative to the project root (assumed to be where run_api.py is)
        current_dir = Path.cwd()
        skills_dir = current_dir / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)

        file_path = skills_dir / f"{skill_name}.md"
        
        # Frontmatter
        frontmatter = {
            "name": skill_name.replace("_", " ").title(),
            "description": description,
        }
        
        yaml_content = yaml.dump(frontmatter, sort_keys=False, allow_unicode=True)
        
        full_content = f"---\n{yaml_content}---\n\n{instructions}\n"
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(full_content)
            
        return f"Successfully created skill workflow '{skill_name}' at {file_path}. The skill will be available upon reload."
    except Exception as e:
        return f"Failed to create skill workflow: {e}"
