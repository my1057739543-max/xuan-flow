"""Tool for invoking executable skills."""

import json
from typing import Any

from langchain_core.tools import tool

from xuan_flow.skills.loader import get_skill_by_name
from xuan_flow.skills.runtime import run_skill_script


@tool("run_skill", parse_docstring=True)
async def run_skill(skill_name: str, args_json: str = "{}") -> str:
    """Run an executable skill by name.

    Use this tool when a task matches a registered skill with scripts.

    Args:
        skill_name: Exact skill name from the available skill list.
        args_json: JSON object string passed to the skill script via stdin.

    Returns:
        JSON string with execution result fields: ok, skill, output, error, exit_code, duration_ms.
    """

    skill = get_skill_by_name(skill_name, enabled_only=True)
    if skill is None:
        return json.dumps({"ok": False, "error": f"Unknown skill: {skill_name}"}, ensure_ascii=False)

    if not skill.entrypoint:
        return json.dumps(
            {
                "ok": False,
                "skill": skill.name,
                "error": "This skill is documentation-only and has no scripts entrypoint.",
            },
            ensure_ascii=False,
        )

    try:
        parsed_args: Any = json.loads(args_json) if args_json.strip() else {}
    except json.JSONDecodeError as e:
        return json.dumps(
            {
                "ok": False,
                "skill": skill.name,
                "error": f"Invalid args_json: {e}",
            },
            ensure_ascii=False,
        )

    if not isinstance(parsed_args, dict):
        return json.dumps(
            {
                "ok": False,
                "skill": skill.name,
                "error": "args_json must decode to a JSON object.",
            },
            ensure_ascii=False,
        )

    result = await run_skill_script(skill=skill, args=parsed_args)
    return json.dumps(result.to_dict(), ensure_ascii=False)
