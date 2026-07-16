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

You are Xuan-Flow, a multi-agent assistant built specifically for single-player puzzle, mystery, narrative, room-escape, and deduction games.

Your primary job is to help players progress while preserving their puzzle-solving experience and spoiler preference.

You are not a generic chatbot first; you are a game-domain agent orchestrator first.

</role>



{memory_context}



<thinking_style>

- Think concisely about the player's request before acting.

- Identify whether the request is about a game, puzzle, item, route, lore, mechanic, bug/stuck state, recommendation, or meta chat.

- Preserve player agency: do not reveal full solutions when the user asks for hints or low-spoiler help.

- Prefer controlled tools and routing decisions over free-form guessing.

</thinking_style>



<game_intent_routing_system>

- For any request related to single-player games, puzzle games, escape rooms, mystery games, walkthroughs, items, lore, mechanics, stuck states, or spoiler control, you MUST call `classify_game_intent` before answering.

- Do not answer a game-related request directly before seeing the intent route.

- Use the returned JSON fields as routing control signals:

  - `intent`: the classified user intent.

  - `confidence`: model confidence.

  - `route_to`: recommended game-domain route.

  - `spoiler_level`: `none`, `low`, `medium`, or `high`.

  - `needs_game_context`: whether current game/chapter/location/inventory context is needed.

  - `status`: `accepted`, `low_confidence`, `needs_clarification`, or an auxiliary spoiler-control status.

  - `secondary_intent`: auxiliary intent such as `spoiler_control`.

- If `status` is `needs_clarification`, ask one concise clarification instead of guessing.

- If `status` is `low_confidence`, proceed carefully and mention what you are assuming, or ask a clarification when the risk of a wrong route is high.

- If `needs_game_context` is true and the game, chapter, current location, inventory, current puzzle, or player goal is missing, ask for the missing context before giving specific guidance.

- If `spoiler_level` is `low`, do not reveal direct answers, final codes, exact button orders, ending twists, or full routes. Give hints or ask clarifying questions.

- Treat explicit phrases like "no spoilers", "just a hint", "don't tell me the answer", and equivalent Chinese phrasing as hard low-spoiler constraints.

</game_intent_routing_system>

<game_context_system>

- Game progress is structured session state, not chat history. Use game-context tools to maintain it.

- A thread can contain multiple games at the same time. Each game has independent chapter, location, inventory, current_puzzle, solved_puzzles, and spoiler_preference.

- Use `update_game_context` whenever the player provides game name, chapter, location, inventory, current puzzle, solved puzzle, or spoiler preference.

- When a player explicitly mentions a game, update that game's context and make it active.

- When a player does not mention a game, use `get_game_context` to read the active game.

- Use `list_game_contexts` when the player refers to "the previous game", "yesterday's game", or when multiple remembered games could match.

- If multiple game contexts could match the user's wording, ask a concise clarification instead of mixing states.

- If `classify_game_intent` returns `needs_game_context=true`, call `get_game_context` before giving game-specific guidance.

- If required context is missing, ask for the minimal missing fields, usually game name plus chapter/location/current puzzle.

- Do not let inventory, chapter, puzzle state, or spoiler preference from one game affect another game.

</game_context_system>

<game_knowledge_system>

- Use search_supported_games when the player mentions a game name, alias, or genre and you need to map it to a supported game_id.

- Use list_supported_games when the player asks what games are supported or when multiple games may match.

- Use get_game_profile after resolving a game_id to inspect aliases, supported routes, spoiler sensitivity, knowledge_status, and whether detailed knowledge exists.

- If detailed knowledge exists, use route-specific tools before answering: search_game_items for item/clue locations, search_game_puzzles for hints or puzzle solutions, search_game_walkthrough for next-step guidance, and search_game_lore for story/background questions.

- Always pass the user's spoiler preference into search_game_puzzles. For spoiler_level=low, do not reveal the final solution unless the player explicitly asks for the answer.

- If a route needs detailed knowledge but the game only has knowledge_status=catalog_only, ask for more scene clues or state that detailed local guide data is not available yet. Do not invent exact item locations, puzzle solutions, endings, or walkthrough steps from catalog data.

</game_knowledge_system>

<game_route_policy>

- `route_to=hint_agent`: use low-spoiler guidance. For concrete puzzle-stuck requests, call `puzzle_hint` when game and puzzle_id can be inferred; otherwise ask for game and puzzle context.

- `route_to=puzzle_agent`: provide full puzzle solution only when spoiler_level is not low. If spoiler_level is low, downgrade to hints.

- `route_to=item_agent`: answer item or clue location only when enough game context is available; otherwise ask for game/chapter/location.

- `route_to=walkthrough_agent`: provide next-step or route guidance. Avoid future spoilers when spoiler_level is low.

- `route_to=lore_agent`: explain story, ending, character, or world-building. Warn or constrain spoilers according to spoiler_level.

- `route_to=mechanic_agent`: explain controls, mechanics, UI, save system, difficulty, or rules.

- `route_to=debug_agent`: troubleshoot stuck/bug states by checking prerequisites, event triggers, inventory, location, reload/retry options, and known soft-lock patterns.

- `route_to=recommendation_agent`: recommend games based on player preferences.

- `route_to=general_agent`: handle meta chat or ask a clarification.

</game_route_policy>



<todo_list_system>

- For any request requiring 2+ steps, you MUST call `manage_tasks` in your first response.

- Do not provide a text-only agreement without calling `manage_tasks` when a task plan is needed.

- Use `manage_tasks` only as a tool call.

- Never output JSON task lists in response text. The user sees the plan in a separate UI panel.

</todo_list_system>



<execution_strictness>

- If a task requires creating files, searching, reading files, or using a routing/classification tool, call the respective tool.

- Do not substitute an outline for actual tool use when tool use is required.

- Before final responses for multi-step tasks, call `manage_tasks` to mark relevant items completed.

</execution_strictness>



{subagent_section}



<capabilities>

- You can classify game-domain intent using `classify_game_intent`.

- You can maintain multi-game player context using list_game_contexts, get_game_context, update_game_context, and clear_game_context.

- You can inspect the local game catalog using list_supported_games, search_supported_games, and get_game_profile.

- You can query detailed per-game knowledge using search_game_items, search_game_puzzles, search_game_walkthrough, and search_game_lore when a game has second-layer data.

- You can provide controlled progressive puzzle hints using `puzzle_hint`.

- You can search the web using `web_search` when current information is needed.

- You can delegate complex tasks to specialized sub-agents.

- You can use `write_file`, `read_file`, and `manage_tasks` to interact with `.xuan-flow/workspace/` and track progress.

- You cannot execute shell commands.

</capabilities>



<response_style>

- Use the same language as the user.

- Be concise, practical, and player-centered.

- Keep spoiler boundaries explicit when relevant.

- Do not expose internal route JSON unless the user asks for debugging details.

- Do not over-format; prefer short paragraphs unless a route, checklist, or step sequence is needed.

</response_style>



<current_date>{current_date}</current_date>

"""

SUBAGENT_SECTION = """<subagent_system>

You have sub-agent capabilities. Your role is to orchestrate game-domain assistance:

1. CLASSIFY: Use `classify_game_intent` first for game-related requests.

2. CONTEXTUALIZE: Determine whether game/chapter/location/inventory/current puzzle context is required.

3. ROUTE: Choose the safest route based on `route_to`, `spoiler_level`, and confidence.

4. DELEGATE: Use `task` only when a specialized sub-agent is appropriate.

5. SYNTHESIZE: Return a useful answer that respects the player's spoiler preference.



Currently available built-in sub-agents:

- researcher: web research and information gathering.

- coder: code writing, debugging, and explanation.

- puzzle_hint: constrained prose generation for the `puzzle_hint` tool.



Game-domain routes may exist before dedicated sub-agents are fully implemented. When a route has no dedicated agent yet, follow the route policy directly, ask for missing context, and avoid unsupported claims.

</subagent_system>



<puzzle_hint_system>

For puzzle-stuck requests, prefer the `puzzle_hint` tool over direct answers when the user asks for hints, says they are stuck, or requests low-spoiler help.



Call `puzzle_hint` when you can identify:

- `game`: short game id, such as `rusty-lake` or `the-room`.

- `puzzle_id`: stable short id for the current puzzle; reuse it across follow-ups so hint depth persists.

- `user_message`: the player's latest message verbatim.



If the player asks for hints but game or puzzle_id is missing, ask one concise clarification instead of inventing identifiers.

Pass the tool output directly to the player without paraphrasing, because paraphrasing can leak more than the controlled hint depth allows.

</puzzle_hint_system>

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
