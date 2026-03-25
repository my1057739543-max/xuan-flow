"""MCP configuration cache mechanisms."""

from xuan_flow.config.app_config import get_app_config


def get_mcp_config_mtime() -> float | None:
    """Get the modification time of the current app config.
    Used to determine if MCP tools need to be reloaded.
    """
    try:
        from xuan_flow.config.app_config import _app_config_mtime
        return _app_config_mtime
    except ImportError:
        return None
