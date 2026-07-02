"""Puzzle hint tool — the anti-spoiler progressive-hint decision layer.

This is the architectural keystone of the single-player puzzle-game assistant.
The RLHF tendency of an LLM is to "be helpful = give the full answer", which
is fatal for a puzzle helper: the moment a player pressures it ("just tell me
the answer!"), a prompt-only assistant caves and spoils the puzzle.

The fix is architectural, not prompt-level: move the decision of *which hint
depth to show* and *whether to escalate* OUT of the LLM and into deterministic
code. The LLM only generates the prose for a depth that code has already
chosen. The solution layer (depth=2) does not exist in the set of reachable
outputs — what does not exist cannot be leaked.

Flow:
    Lead Agent (LLM routing) → puzzle_hint tool (this module, code decisions)
        → SubagentExecutor(puzzle_hint agent) → constrained prose back to user
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# ── State persistence ────────────────────────────────────────────────────────

PUZZLES_FILE = Path.cwd() / ".xuan-flow" / "puzzles.json"

MAX_DEPTH = 1  # depth ∈ {0, 1}; depth=2 (solution layer) is intentionally unreachable

Signal = Literal["escalate", "resolve", "pressure", "other"]
Mode = Literal["hint", "scaffold"]


def _empty_state() -> dict[str, Any]:
    return {"version": "1.0", "puzzles": {}}


def _load_puzzles() -> dict[str, Any]:
    """Load puzzle state JSON (best-effort, fault-tolerant)."""
    if not PUZZLES_FILE.exists():
        return _empty_state()
    try:
        with open(PUZZLES_FILE, encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("puzzles"), dict):
                return data
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load puzzles state: %s", e)
    return _empty_state()


def _save_puzzles(state: dict[str, Any]) -> None:
    """Atomically persist puzzle state."""
    try:
        PUZZLES_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = PUZZLES_FILE.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        tmp.replace(PUZZLES_FILE)
    except OSError as e:
        logger.error("Failed to save puzzles state: %s", e)


# ── Signal classification (formalized, NOT LLM-judged) ───────────────────────
# Order matters: pressure is checked BEFORE escalate, because a phrase like
# "求你了直接告诉我" contains neither escalate nor resolve markers but is
# clearly pressure. Escalate markers ("还是不懂") are explicit non-answer
# requests. Pressure markers ("直接说答案") must NOT trigger escalation —
# that is the whole point of the anti-RLHF design.

# Resolve: player indicates understanding / will try themselves / done.
_RESOLVE_RE = re.compile(
    r"懂了|明白了|会了|过了|我去试试|试试看|搞定了|搞懂了|谢谢你|谢谢|"
    r"我自己来|我自己试|不用提示了|解决了|想通了",
)

# Escalate: player is asking for help / a (deeper) hint — NOT for the answer.
# Covers both first-time "I'm stuck" and follow-up "still don't get it".
# A stuck signal on an already-resolved puzzle reopens the puzzle (see
# already_resolved handling below) — the player is stuck again.
_ESCALATE_RE = re.compile(
    r"还是不懂|不明白|没懂|没明白|想不出来|想不通|"
    r"再提示|再给点|继续提示|更具体|再深一点|还是不会|看不懂|"
    r"卡住|卡了|过不去|过不了|不知道怎么过|不知道怎么做|"
    r"求助|帮帮我|怎么过|怎么解|解不开|没头绪|又卡了|再次卡住",
)

# Pressure: player begs/demands the answer or claims to give up.
# This is the dangerous category — must NEVER escalate to the solution layer.
_PRESSURE_RE = re.compile(
    r"求你|求了|直接告诉我|直接说|告诉我答案|给我答案|剧透|"
    r"放弃|放弃了|受不了|受不了了|我给你钱|奖励你|"
    r"到底怎么|到底答案|查攻略|求求你",
)


def _classify_signal(user_message: str) -> Signal:
    """Classify the player's latest message into a routing signal.

    Pure regex, fully deterministic — this is the gate that keeps RLHF out.
    Priority: resolve > pressure > escalate > other.
    """
    if not user_message:
        return "other"
    text = user_message.strip()

    # Pressure is checked before escalate: a message can contain both a vague
    # "看不懂" and a hard "直接告诉我答案" — the demand for the answer wins
    # and we hold the line rather than escalating.
    if _PRESSURE_RE.search(text):
        return "pressure"
    if _RESOLVE_RE.search(text):
        return "resolve"
    if _ESCALATE_RE.search(text):
        return "escalate"
    return "other"


# ── Depth decision (state machine, NOT LLM-judged) ──────────────────────────


def _decide_depth(
    current_depth: int, current_mode: Mode, signal: Signal
) -> tuple[int, Mode, bool]:
    """Decide the next (depth, mode, resolved) given current state + signal.

    Rules (the contract the whole anti-spoiler guarantee rests on):
      - pressure / other            → depth unchanged, mode unchanged   (hold the line)
      - escalate, depth < MAX_DEPTH → depth + 1, mode 'hint'
      - escalate, depth == MAX      → depth unchanged, mode 'scaffold'   (deeper help, still not the answer)
      - resolve                     → depth unchanged, mode unchanged, resolved=True
    """
    if signal == "resolve":
        return current_depth, current_mode, True

    if signal == "escalate":
        if current_depth < MAX_DEPTH:
            return current_depth + 1, "hint", False
        # Already at max hint depth: switch to scaffold mode instead of
        # inventing a forbidden solution layer.
        return current_depth, "scaffold", False

    # pressure or other → hold
    return current_depth, current_mode, False


# ── Layer-prompt construction ────────────────────────────────────────────────

LAYER_DESCRIPTIONS = {
    (0, "hint"): (
        "方向层(depth=0)：只点明玩家「该往哪看、该观察什么」，不解释谜题机制，"
        "不给任何操作。例：「注意墙上水位刻度的排列」。"
    ),
    (1, "hint"): (
        "机制层(depth=1)：解释谜题如何运作的逻辑，但不给具体操作序列或数值。"
        "例：「刻度对应齿轮转动次数，需要从别处找到转动次数的提示」，"
        "不可说「转三次」。"
    ),
    (1, "scaffold"): (
        "脚手架模式(depth=1)：苏格拉底式追问，引导玩家自己定位卡点。"
        "问「你手上有哪些道具？」「你试过哪些组合？」「卡在哪一步——是不知道做什么，还是做了没反应？」"
        "绝不替玩家走完，绝不给具体步骤。"
    ),
}


# ── Puzzle reference material ────────────────────────────────────────────────
# Each game has a SKILL.md under skills/public/<game>-hints/ structured with
# sections "## 谜题：<puzzle_id> (...)". The tool extracts the relevant
# section and injects it as context for the sub-agent — which has no tool
# access of its own, so it cannot go looking for answers elsewhere.

_HINTS_ROOT = Path.cwd() / "skills" / "public"

# Map game id → hints skill directory name.
_GAME_HINTS_DIR = {
    "rusty-lake": "rusty-lake-hints",
}


def _load_puzzle_context(game: str, puzzle_id: str) -> str:
    """Load the reference-material section for one puzzle, if available.

    Returns an empty string when no material exists — the sub-agent then falls
    back to its own knowledge of the game. Material, when present, is layered
    hint guidance (direction / mechanism / scaffold), never the solution.
    """
    dir_name = _GAME_HINTS_DIR.get(game)
    if not dir_name:
        return ""
    skill_file = _HINTS_ROOT / dir_name / "SKILL.md"
    if not skill_file.exists():
        return ""

    try:
        text = skill_file.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning("Failed to read puzzle hints for %s: %s", game, e)
        return ""

    # Extract the section "## 谜题：<puzzle_id>" up to the next "## 谜题：" or
    # "---" separator or end of file.
    marker = f"## 谜题：{puzzle_id}"
    start = text.find(marker)
    if start == -1:
        return ""
    end = text.find("\n## 谜题：", start + len(marker))
    section = text[start:] if end == -1 else text[start:end]

    # Strip the heading line and surrounding whitespace.
    lines = section.splitlines()
    body = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
    return body


def _build_subagent_prompt(
    game: str,
    puzzle_id: str,
    user_message: str,
    depth: int,
    mode: Mode,
    resolved: bool,
    puzzle_context: str = "",
) -> str:
    """Construct the prompt for the puzzle_hint sub-agent.

    The sub-agent is given ONLY the layer to generate — it cannot see or
    change the depth/mode decision. That decision is final in this prompt.
    """
    layer_desc = LAYER_DESCRIPTIONS.get((depth, mode), LAYER_DESCRIPTIONS[(0, "hint")])

    if resolved:
        return (
            f"玩家表示已经明白了谜题 [{game}:{puzzle_id}]。\n"
            f"请给一句简短的鼓励性收尾，确认玩家过关，不重复任何提示内容。"
            f"玩家原话：「{user_message}」"
        )

    context_block = ""
    if puzzle_context:
        context_block = (
            f"\n以下是该谜题的参考素材（仅用于指导你生成对应层级，"
            f"不可输出其中的解法性内容）：\n{puzzle_context}\n"
        )

    return (
        f"玩家正在求助谜题 [{game}:{puzzle_id}]。\n"
        f"玩家最新消息：「{user_message}」\n"
        f"{context_block}\n"
        f"本次你被指定输出的层级：\n{layer_desc}\n\n"
        f"严格按上述层级规范生成提示文案。只输出提示文案本身，"
        f"不要解释你的层级机制，不要输出 JSON 或元信息。"
    )


# ── Tool entry ───────────────────────────────────────────────────────────────


@tool("puzzle_hint", parse_docstring=True)
async def puzzle_hint(
    game: str,
    puzzle_id: str,
    user_message: str,
) -> str:
    """Provide a progressive, anti-spoiler hint for a single-player puzzle game.

    Use this when a player is stuck on a puzzle and asks for help. The tool
    tracks per-puzzle hint depth across sessions and escalates ONLY on the
    player's explicit request ("still don't get it"). It never reveals the
    full solution, even under pressure.

    Args:
        game: Game identifier, e.g. "rusty-lake".
        puzzle_id: Puzzle identifier within the game, e.g. "water-valve".
        user_message: The player's latest message verbatim.

    Returns:
        The generated hint text for the current depth, or an acknowledgement
        if the puzzle was marked resolved.
    """
    state = _load_puzzles()
    key = f"{game}:{puzzle_id}"
    record = state["puzzles"].get(key, {
        "depth": 0,
        "mode": "hint",
        "resolved": False,
        "escalation_count": 0,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    })

    signal = _classify_signal(user_message)
    new_depth, new_mode, resolved = _decide_depth(
        int(record.get("depth", 0)),
        record.get("mode", "hint"),  # type: ignore[arg-type]
        signal,
    )

    # If the puzzle was previously resolved, the player re-opening it
    # (explicit stuck/escalate signal) means the prior "resolved" no longer
    # holds — reset it and re-hint. Only a non-help, non-resolve message
    # (e.g. idle follow-up) on a resolved puzzle takes the acknowledgement
    # branch.
    already_resolved = bool(record.get("resolved", False))
    if already_resolved and signal not in ("escalate", "pressure"):
        return (
            f"根据记录，你之前已经通过了谜题 [{game}:{puzzle_id}]。"
            "如果卡在别的地方，告诉我新的谜题就行。"
        )
    reopened = already_resolved and signal == "escalate"

    # Reopening a resolved puzzle starts a fresh hint cycle from depth 0 —
    # the player is stuck again and may have forgotten earlier hints.
    if reopened:
        new_depth = 0
        new_mode = "hint"

    record["depth"] = new_depth
    record["mode"] = new_mode
    # resolve sets it True; escalate reopens (False); others keep prior value.
    record["resolved"] = False if reopened else (already_resolved or resolved)
    if signal == "escalate":
        record["escalation_count"] = int(record.get("escalation_count", 0)) + 1
    record["last_updated"] = datetime.now(timezone.utc).isoformat()
    state["puzzles"][key] = record
    _save_puzzles(state)

    # Pressure gets a gentle, fixed holding-line preamble prepended to the
    # scaffold question — so the player feels heard, not stonewalled, while
    # the actual hint content stays non-spoilery.
    pressure_preamble = ""
    if signal == "pressure":
        pressure_preamble = (
            "我知道你卡得很难受，但我不会直接告诉你答案——解谜的乐趣正在于此。"
            "换个方式陪你推进："
        )

    prompt = _build_subagent_prompt(
        game=game,
        puzzle_id=puzzle_id,
        user_message=user_message,
        depth=new_depth,
        mode=new_mode,  # type: ignore[arg-type]
        resolved=bool(record["resolved"]),
        puzzle_context=_load_puzzle_context(game, puzzle_id),
    )

    # Delegate prose generation to the constrained sub-agent.
    try:
        from xuan_flow.subagents.executor import SubagentExecutor
        from xuan_flow.subagents.registry import get_subagent_config

        config = get_subagent_config("puzzle_hint")
        if config is None:
            return "提示系统未配置（puzzle_hint 子 agent 缺失）。"
        executor = SubagentExecutor(config=config)
        result = await executor.execute(task=prompt)
        if result.error:
            logger.warning("puzzle_hint sub-agent failed: %s", result.error)
            return "提示生成失败，请稍后重试。"
        prose = (result.result or "").strip()
    except Exception as e:
        logger.exception("puzzle_hint sub-agent invocation failed: %s", e)
        return "提示生成失败，请稍后重试。"

    logger.info(
        "puzzle_hint: game=%s puzzle=%s signal=%s depth=%d mode=%s",
        game, puzzle_id, signal, new_depth, new_mode,
    )

    return f"{pressure_preamble}{prose}" if pressure_preamble else prose
