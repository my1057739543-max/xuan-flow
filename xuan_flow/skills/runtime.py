"""Runtime for executing directory-based skill scripts."""

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any

from xuan_flow.skills.types import Skill


@dataclass
class SkillRunResult:
    """Normalized execution result for a skill script run."""

    ok: bool
    skill_name: str
    output: str = ""
    error: str = ""
    exit_code: int | None = None
    duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "skill": self.skill_name,
            "output": self.output,
            "error": self.error,
            "exit_code": self.exit_code,
            "duration_ms": self.duration_ms,
        }


async def run_skill_script(skill: Skill, args: dict[str, Any] | None = None, timeout_seconds: int = 60) -> SkillRunResult:
    """Execute a skill's Node.js entrypoint and return normalized output."""

    start = time.time()
    args = args or {}

    if not skill.scripts_dir or not skill.entrypoint:
        return SkillRunResult(
            ok=False,
            skill_name=skill.name,
            error="Skill has no executable scripts configured.",
            duration_ms=int((time.time() - start) * 1000),
        )

    entry_script = (skill.scripts_dir / skill.entrypoint).resolve()
    if not entry_script.exists():
        return SkillRunResult(
            ok=False,
            skill_name=skill.name,
            error=f"Entrypoint not found: {entry_script}",
            duration_ms=int((time.time() - start) * 1000),
        )

    payload = json.dumps(args, ensure_ascii=False)

    try:
        process = await asyncio.create_subprocess_exec(
            "node",
            str(entry_script),
            cwd=str(skill.skill_dir.resolve()),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        return SkillRunResult(
            ok=False,
            skill_name=skill.name,
            error="Node.js executable not found. Install Node.js in runtime environment.",
            duration_ms=int((time.time() - start) * 1000),
        )

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(payload.encode("utf-8")),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        return SkillRunResult(
            ok=False,
            skill_name=skill.name,
            error=f"Skill execution timed out after {timeout_seconds}s",
            duration_ms=int((time.time() - start) * 1000),
        )

    stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
    stderr = stderr_bytes.decode("utf-8", errors="replace").strip()
    code = process.returncode

    return SkillRunResult(
        ok=code == 0,
        skill_name=skill.name,
        output=stdout,
        error=stderr if code != 0 else "",
        exit_code=code,
        duration_ms=int((time.time() - start) * 1000),
    )
