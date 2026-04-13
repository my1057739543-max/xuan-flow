"""Tool registry — assembles the list of tools available to agents."""

from langchain_core.tools import BaseTool

from xuan_flow.tools.web_search import web_search
from xuan_flow.tools.web_fetch import web_fetch_content


async def get_available_tools(subagent_enabled: bool = False, exclude_task: bool = False) -> list[BaseTool]:
    """Get all available tools for an agent.

    Args:
        subagent_enabled: If True, include the task() delegation tool.
        exclude_task: If True, force-exclude task tool (for sub-agents).

    Returns:
        List of LangChain tools.
    """
    from xuan_flow.tools.file_tools import read_file, write_file, delete_file
    from xuan_flow.tools.task_management import manage_tasks, get_task_list
    from xuan_flow.tools.clarification_tool import ask_clarification
    from xuan_flow.tools.skill_creator import create_skill_workflow
    from xuan_flow.tools.skill_runner import run_skill
    from xuan_flow.tools.image_inspector import inspect_image_metadata
    from xuan_flow.mcp.tools import get_mcp_tools

    tools: list[BaseTool] = [
        web_search, 
        web_fetch_content,
        write_file, 
        read_file, 
        delete_file,
        manage_tasks,
        get_task_list,
        ask_clarification, 
        create_skill_workflow, 
        run_skill,
        inspect_image_metadata
    ]

    if subagent_enabled and not exclude_task:
        from xuan_flow.tools.task_tool import task
        tools.append(task)
        
    # Asynchronously load MCP tools (no-op or returns cache if ready)
    if not exclude_task:
        try:
            mcp_tools = await get_mcp_tools()
            if mcp_tools:
                tools.extend(mcp_tools)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Failed to load MCP tools: %s", e)

    return tools
