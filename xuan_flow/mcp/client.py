"""Build MCP client configurations."""

import logging
from typing import Any

from xuan_flow.config.app_config import get_app_config

logger = logging.getLogger(__name__)


def build_servers_config() -> dict[str, dict[str, Any]]:
    """Build the configuration dict required by MultiServerMCPClient from our AppConfig.

    Returns:
        dict: The config dict mapping server names to their transport configs.
    """
    config = get_app_config()
    mcp_servers = config.mcp_servers or {}
    
    servers_config: dict[str, dict[str, Any]] = {}

    for server_name, server_data in mcp_servers.items():
        if not isinstance(server_data, dict):
            logger.warning("Invalid configuration for MCP server '%s'", server_name)
            continue
            
        transport = server_data.get("transport")
        if transport not in ("stdio", "sse", "http"):
            logger.warning("Invalid or missing transport for MCP server '%s': %s", server_name, transport)
            continue
            
        server_config = {"transport": transport}
        
        if transport == "stdio":
            command = server_data.get("command")
            if not command:
                logger.warning("Missing 'command' for stdio MCP server '%s'", server_name)
                continue
                
            server_config["command"] = command
            server_config["args"] = server_data.get("args", [])
            if "env" in server_data:
                server_config["env"] = server_data["env"]
                
        elif transport in ("sse", "http"):
            url = server_data.get("url")
            if not url:
                logger.warning("Missing 'url' for %s MCP server '%s'", transport, server_name)
                continue
                
            server_config["url"] = url
            if "headers" in server_data:
                server_config["headers"] = server_data["headers"]

        servers_config[server_name] = server_config

    return servers_config
