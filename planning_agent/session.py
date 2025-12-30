from __future__ import annotations

import uuid
from typing import Any, Optional
from mcp.server.fastmcp import Context

# Use a context var or simple global for the current session
_current_session_id: str = "default"
_session_data: dict[str, dict[str, Any]] = {}


def get_session_id(ctx: Optional[Context] = None) -> str:
    """Get the session ID from MCP context or return default."""
    if ctx and hasattr(ctx, "session_id") and ctx.session_id:
        return str(ctx.session_id)
    
    # Try to get from metadata if available
    if ctx and hasattr(ctx, "request_context") and ctx.request_context:
        # Some MCP implementations might store it here
        pass
        
    return _current_session_id


def set_current_session(session_id: str) -> None:
    global _current_session_id
    _current_session_id = session_id


def get_current_session() -> str:
    return _current_session_id


def get_session_context(session_id: str) -> dict[str, Any]:
    """Get context data for a session."""
    return _session_data.setdefault(session_id, {
        "current_pov": {},
        "recent_queries": [],
        "variables": {}
    })


def update_session_context(session_id: str, updates: dict[str, Any]) -> None:
    """Update context data for a session."""
    context = get_session_context(session_id)
    context.update(updates)
