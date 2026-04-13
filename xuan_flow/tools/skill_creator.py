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
                # Resolve skills directory relative to project root.
        current_dir = Path.cwd()
                skills_dir = current_dir / "skills" / "custom"
        skills_dir.mkdir(parents=True, exist_ok=True)

                safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in skill_name.strip().lower()).strip("-")
                if not safe_name:
                        return "Failed to create skill workflow: invalid skill_name"

                skill_dir = skills_dir / safe_name
                scripts_dir = skill_dir / "scripts"
                scripts_dir.mkdir(parents=True, exist_ok=True)

                config_path = skill_dir / "config.yaml"
                doc_path = skill_dir / "SKILL.md"
                script_path = scripts_dir / "main.js"

                config_data = {
                        "name": safe_name,
            "description": description,
                        "entrypoint": "main.js",
                        "enabled": True,
                        "invocation_hint": f"Use this skill when user asks for {safe_name} workflow execution.",
        }

                config_path.write_text(yaml.dump(config_data, sort_keys=False, allow_unicode=True), encoding="utf-8")
                doc_path.write_text(f"# {safe_name}\n\n{instructions}\n", encoding="utf-8")

                script_content = """const fs = require('fs');

function readInput() {
    try {
        const data = fs.readFileSync(0, 'utf8');
        return data && data.trim() ? JSON.parse(data) : {};
    } catch (err) {
        return {};
    }
}

const input = readInput();
const result = {
    ok: true,
    skill: process.env.SKILL_NAME || 'custom-skill',
    received: input,
    message: 'Skill script executed successfully.'
};

process.stdout.write(JSON.stringify(result));
"""
                script_path.write_text(script_content, encoding="utf-8")

                return f"Successfully created skill workflow '{safe_name}' at {skill_dir}. The skill will be available upon reload."
    except Exception as e:
        return f"Failed to create skill workflow: {e}"
