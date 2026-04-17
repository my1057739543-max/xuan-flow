"""Lead Agent — the central orchestrator for Xuan-Flow.

Inspired by deer-flow's lead_agent: creates a LangGraph ReAct agent with
dynamic system prompt (memory + subagent instructions), tool assembly,
and middleware chain.
"""

import logging
from datetime import datetime
import json
import re

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage, ToolMessage, AIMessage
from langgraph.prebuilt import create_react_agent

from xuan_flow.agents.thread_state import ThreadState
from xuan_flow.config.app_config import get_app_config
from xuan_flow.memory.store import (
    format_memory_for_injection,
    get_memory_data,
    rebuild_working_memory,
    get_working_memory_markdown,
)
from xuan_flow.models.factory import create_chat_model
from xuan_flow.subagents.registry import get_subagent_names
from xuan_flow.tools.registry import get_available_tools

logger = logging.getLogger(__name__)


def _save_tasks_file(tasks: list[dict]) -> None:
    """Persist tasks for frontend Execution Plan sync."""
    try:
        from xuan_flow.tools.task_management import TASKS_FILE

        TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TASKS_FILE, "w", encoding="utf-8") as f:
            json.dump(tasks, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning("Failed to persist bootstrap tasks: %s", e)


def _infer_initial_tasks(query: str) -> list[dict]:
    """Infer a minimal execution plan from the user query.

    This is a deterministic fallback when the model skips manage_tasks.
    """
    text = (query or "").strip()
    if not text:
        return []

    # Prefer explicit numbered/bulleted instructions when present.
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    extracted: list[str] = []
    for ln in lines:
        if re.match(r"^(\d+[\.)]|[-*•])\s+", ln):
            extracted.append(re.sub(r"^(\d+[\.)]|[-*•])\s+", "", ln).strip())

    if extracted:
        tasks = [
            {"content": item[:180], "status": "pending"}
            for item in extracted[:8]
            if item
        ]
        if tasks:
            tasks[0]["status"] = "in_progress"
        return tasks

    # Generic fallback for short/simple prompts.
    short = re.sub(r"\s+", " ", text)[:180]
    return [{"content": f"Handle request: {short}", "status": "in_progress"}]


def _mark_tasks_completed(tasks: list[dict]) -> list[dict]:
    """Mark all active tasks as completed for final UI state."""
    completed = []
    for task in tasks:
        item = dict(task)
        item["status"] = "completed"
        completed.append(item)
    return completed


# ── System Prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT_TEMPLATE = """<role>
You are Xuan-Flow, a lightweight multi-agent assistant.
</role>

{memory_context}

<thinking_style>
- Think concisely about the user's request before acting
- Break down: What is clear? What needs clarification?
- Focus on delivering results, not explaining processes
</thinking_style>

<todo_list_system>
- **MANDATORY INITIATION**: For any request requiring 2+ steps, you MUST call `manage_tasks` in your **VERY FIRST response**. 
- **NO TEXT-ONLY STARTS**: Do not provide a text-only agreement (e.g. "Sure, I will do that") without calling `manage_tasks` at the same time.
- **INTERNAL TOOL ONLY**: Use `manage_tasks` ONLY as a tool call. 
- **NO JSON IN RESPONSE**: NEVER output JSON-formatted task lists or code blocks in your response text. The user sees the plan in a separate UI panel.
</todo_list_system>

<execution_strictness>
- **ANTI-LAZINESS**: You are forbidden from giving partial results or summaries when full content is requested.
- **TOOL-FIRST**: If a task requires creating files, searching, or running code, you MUST call the respective tools. NEVER just "outline" the content in your response as a substitute for actual file operations.
- **VERIFICATION**: Before your final response, verify EVERY file you promised to create actually exists in the workspace.
- **MANDATORY SYNC**: You must call `manage_tasks` to mark items as 'completed' before you provide the final response for those items.
</execution_strictness>

{subagent_section}

<capabilities>
- You can search the web for information using the web_search tool
- You can delegate complex tasks to specialized sub-agents
- You have a local workspace directory to save files: `.xuan-flow/workspace/`
- You can use `write_file`, `read_file`, and `manage_tasks` to interact with your workspace and track progress.
- When a user asks you to generate a file, you MUST write it to your workspace using `write_file`.
- You CANNOT execute code or commands.
</capabilities>

<response_style>
- Clear and concise, avoid over-formatting
- Natural tone with paragraphs, not bullet points by default
- Action-oriented: deliver results, don't narrate your process
- Use the same language as the user
</response_style>

<current_date>{current_date}</current_date>
"""

SUBAGENT_SECTION = """<subagent_system>
You have sub-agent capabilities. Your role is to be a task orchestrator:
1. DECOMPOSE: Break complex tasks into sub-tasks
2. DELEGATE: Use the `task` tool to delegate to specialized sub-agents
3. SYNTHESIZE: Collect results and provide a coherent answer

Available sub-agents:
- **researcher**: For web research, information gathering, and summarization
- **coder**: For code writing, debugging, and explanations

When to use sub-agents:
✅ Complex questions requiring research from multiple angles
✅ Tasks with separate independent sub-components
✅ Mixed tasks needing both research and coding

When NOT to use sub-agents:
❌ Simple, direct questions you can answer yourself
❌ Tasks that can't be meaningfully decomposed
❌ Pure chat / conversational responses
</subagent_system>
"""


def _get_skills_prompt_section() -> str:
    """Generate the <skill_system> prompt section."""
    try:
        from xuan_flow.skills.loader import load_skills
        skills = load_skills(enabled_only=True)
        if not skills:
            return ""

        skill_items = "\n".join(
            (
                f"    <skill>\n"
                f"        <name>{s.name}</name>\n"
                f"        <description>{s.description}</description>\n"
                f"        <location>{s.get_workspace_file_path()}</location>\n"
                f"        <entry_script>{s.get_entry_script_path() or ''}</entry_script>\n"
                f"        <invocation_hint>{s.invocation_hint or ''}</invocation_hint>\n"
                f"    </skill>"
            )
            for s in skills
        )

        return f"""<skill_system>
You have access to predefined skills that provide workflows and instructions for specific tasks.
When a query matches a skill, first call `read_file` on the skill location to learn the workflow.
If the skill has an entry script, execute it via `run_skill` with JSON args.
<available_skills>
{skill_items}
</available_skills>
</skill_system>"""
    except Exception as e:
        logger.warning("Failed to load skills prompt: %s", e)
        return ""


def _build_system_prompt(subagent_enabled: bool = True) -> str:
    """Build the system prompt with dynamic memory and subagent sections."""

    # Memory injection
    config = get_app_config()
    memory_context = ""
    if config.memory.enabled:
        try:
            memory_data = get_memory_data()
            memory_content = format_memory_for_injection(
                memory_data,
                max_facts=config.memory.max_injection_facts,
            )
            if memory_content.strip():
                memory_context = f"<memory>\n{memory_content}\n</memory>"
        except Exception as e:
            logger.warning("Failed to load memory: %s", e)

    # Subagent section
    subagent_section = SUBAGENT_SECTION if subagent_enabled else ""

    # Skills section
    skills_context = _get_skills_prompt_section()

    return SYSTEM_PROMPT_TEMPLATE.format(
        memory_context=f"{memory_context}\n\n{skills_context}",
        subagent_section=subagent_section,
        current_date=datetime.now().strftime("%Y-%m-%d, %A"),
    )


# ── Agent Nodes ──────────────────────────────────────────────────────────────

import time
from xuan_flow.utils.trace_logger import save_trace

async def _call_model(state: ThreadState, model, system_prompt: str):
    """Refined model call node with dynamic task state injection."""
    start_time = time.time()
    logger.info("\n" + "="*50 + "\n[NODE: AGENT] 🧠 Thinking...\n" + "="*50)
    messages = list(state.get("messages", []))
    tasks = state.get("tasks", [])
    
    # If we have tasks, inject an ephemeral reminder into the context
    if tasks:
        logger.info(f"Context: Found {len(tasks)} tasks in state. Injecting reminder.")
        formatted_tasks = "\n".join([f"    - [{t.get('status', 'pending')}] {t.get('content')}" for t in tasks])
        reminder_content = f"""<todo_list_context>
Your current execution plan's state:
{formatted_tasks}

**REMINDER**: You must mark all relevant tasks as 'completed' via `manage_tasks` before providing your final response to the user.
</todo_list_context>"""
        # Inject as a system message right before the latest turn
        messages.append(SystemMessage(content=reminder_content))
    else:
        logger.info("Context: No active tasks in state.")

    # Build and inject L2 working memory for the current request.
    try:
        config = get_app_config()
        if config.memory.enabled:
            latest_user_query = _extract_latest_user_query(messages)
            rebuild_working_memory(
                query=latest_user_query,
                max_facts=config.memory.max_injection_facts,
            )
            working_memory = get_working_memory_markdown().strip()
            if working_memory:
                messages.append(SystemMessage(content=f"<working_memory>\n{working_memory}\n</working_memory>"))
    except Exception as e:
        logger.warning("Failed to build working memory: %s", e)
    
    # Prepare the actual prompt (first message should be system)
    if not any(isinstance(m, SystemMessage) for m in messages):
        messages.insert(0, SystemMessage(content=system_prompt))
        
    response = await model.ainvoke(messages)
    duration = time.time() - start_time
    
    trace_entry = {"node": "agent", "duration": round(duration, 3), "timestamp": start_time}
    new_trace = state.get("trace", []) + [trace_entry]
    save_trace(new_trace)
    
    updated_tasks = tasks
    if response.tool_calls:
        logger.info(f"Outcome: Agent decided to CALL TOOLS: {[t['name'] for t in response.tool_calls]}")
    else:
        logger.info("Outcome: Agent provided a DIRECT RESPONSE.")
        if tasks:
            # Deterministic fallback: close remaining tasks on final answer.
            updated_tasks = _mark_tasks_completed(tasks)
            _save_tasks_file(updated_tasks)
        
    return {
        "messages": [response],
        "trace": [trace_entry],
        "tasks": updated_tasks,
    }


async def _bootstrap_tasks(state: ThreadState):
    """Initialize execution tasks before the first model turn.

    This guarantees Execution Plan visibility even if the model skips manage_tasks.
    """
    existing = state.get("tasks", [])
    if existing:
        return {}

    query = _extract_latest_user_query(list(state.get("messages", [])))
    initial_tasks = _infer_initial_tasks(query)
    if not initial_tasks:
        return {}

    _save_tasks_file(initial_tasks)
    logger.info("Bootstrap: seeded %s task(s) before first model turn.", len(initial_tasks))
    return {"tasks": initial_tasks}


def _extract_latest_user_query(messages: list) -> str:
    """Best-effort extraction of latest user message for memory ranking."""
    for msg in reversed(messages):
        role = type(msg).__name__.lower()
        if "human" in role:
            content = getattr(msg, "content", "")
            if isinstance(content, str) and content.strip():
                return content.strip()
    return ""


async def _call_tools(state: ThreadState, tools_list):
    """Tool execution node with State synchronization."""
    start_time = time.time()
    logger.info("\n" + "-"*50 + "\n[NODE: TOOLS] 🛠️ Executing...\n" + "-"*50)
    
    # Use standard ToolNode for execution
    tool_node = ToolNode(tools_list)
    result = await tool_node.ainvoke(state)
    
    # Post-process tool outputs to update 'tasks' state if manage_tasks was called
    new_tasks = state.get("tasks", [])
    tool_messages = result.get("messages", [])
    tool_names = []
    
    for msg in tool_messages:
        if isinstance(msg, ToolMessage):
            tool_names.append(msg.name)
            try:
                # Check for manage_tasks output patterns
                data = json.loads(msg.content)
                if "tasks" in data:
                    logger.info("Post-Sync: Task list update detected. Syncing internal state...")
                    new_tasks = data["tasks"]
            except:
                pass # Not a JSON task update, skip
    
    duration = time.time() - start_time
    trace_entry = {"node": "tools", "duration": round(duration, 3), "timestamp": start_time, "tools": list(set(tool_names))}
    new_trace = state.get("trace", []) + [trace_entry]
    save_trace(new_trace)
    
    return {
        "messages": tool_messages, 
        "tasks": new_tasks,
        "trace": [trace_entry]
    }


def _should_continue(state: ThreadState):
    """Edge logic to decide between Tool use and End of turn."""
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        logger.info("Next Step: -> [Routing to TOOLS]")
        return "tools"
    
    logger.info("Next Step: -> [Routing to END]")
    return END


# ── Agent Factory ────────────────────────────────────────────────────────────

async def make_lead_agent(
    model_name: str | None = None,
    subagent_enabled: bool | None = None,
):
    """Create the Lead Agent (Custom StateGraph)."""
    config = get_app_config()
    if subagent_enabled is None:
        subagent_enabled = config.subagents.enabled

    model = create_chat_model(name=model_name)
    tools = await get_available_tools(subagent_enabled=subagent_enabled)
    
    # CRITICAL FIX: Bind tools to the model so it knows it can call them!
    model_with_tools = model.bind_tools(tools)
    
    system_prompt = _build_system_prompt(subagent_enabled=subagent_enabled)

    # Build the StateGraph
    workflow = StateGraph(ThreadState)
    
    # Define node wrappers to handle closures and async execution correctly
    async def bootstrap_tasks_node(state: ThreadState):
        return await _bootstrap_tasks(state)

    async def agent_node(state: ThreadState):
        return await _call_model(state, model_with_tools, system_prompt)

    async def tools_node(state: ThreadState):
        return await _call_tools(state, tools)
    
    # Add nodes
    workflow.add_node("bootstrap_tasks", bootstrap_tasks_node)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tools_node)
    
    # Add edges
    workflow.add_edge(START, "bootstrap_tasks")
    workflow.add_edge("bootstrap_tasks", "agent")
    workflow.add_conditional_edges("agent", _should_continue, {"tools": "tools", END: END})
    workflow.add_edge("tools", "agent")

    logger.info(
        "Creating State-Driven Lead Agent: model=%s, subagent_enabled=%s",
        model_name or config.models[0].name if config.models else "none",
        subagent_enabled
    )

    return workflow.compile()
