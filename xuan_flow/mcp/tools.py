"""Load MCP tools using langchain-mcp-adapters."""

import logging
from typing import Any

from langchain_core.tools import BaseTool

from xuan_flow.mcp.client import build_servers_config
from xuan_flow.mcp.cache import get_mcp_config_mtime

logger = logging.getLogger(__name__)

# Global cache to reuse MCP client across invocations
_mcp_client_cache: Any = None
_mcp_tools_cache: list[BaseTool] | None = None
_mcp_cache_mtime: float | None = None


async def get_mcp_tools() -> list[BaseTool]:
    """Get all tools from enabled MCP servers.

    Caches the loaded tools and reloads them if config.yaml changes.

    Returns:
        List of LangChain tools from all MCP servers.
    """
    global _mcp_client_cache, _mcp_tools_cache, _mcp_cache_mtime
    
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except ImportError:
        logger.warning("langchain-mcp-adapters not installed. Install it to enable MCP tools.")
        return []

    current_mtime = get_mcp_config_mtime()
    
    # Return cache if valid
    if _mcp_tools_cache is not None and _mcp_cache_mtime == current_mtime:
        return _mcp_tools_cache

    # Rebuild tools
    servers_config = build_servers_config()
    if not servers_config:
        logger.debug("No MCP servers configured.")
        _mcp_tools_cache = []
        _mcp_cache_mtime = current_mtime
        if _mcp_client_cache:
            # Need to close old connections ideally, but MultiServerMCPClient doesn't have an explicit close
            _mcp_client_cache = None
        return []

    try:
        logger.info("Initializing MCP client with %d server(s)", len(servers_config))
        client = MultiServerMCPClient(servers_config, tool_name_prefix=True)
        tools = await client.get_tools()
        
        logger.info("Successfully loaded %d tool(s) from MCP servers", len(tools))
        
        _mcp_client_cache = client
        _mcp_tools_cache = tools
        _mcp_cache_mtime = current_mtime
        return tools
    except Exception as e:
        logger.error("Failed to load MCP tools: %s", e, exc_info=True)
        return []
