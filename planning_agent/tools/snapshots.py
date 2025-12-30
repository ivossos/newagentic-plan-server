"""Snapshot tools - get_snapshots."""

from typing import Any

from planning_agent.client.planning_client import PlanningClient

_client: PlanningClient = None


def set_client(client: PlanningClient):
    global _client
    _client = client


async def get_snapshots() -> dict[str, Any]:
    """Get list of application snapshots from the EPM instance / Obter lista de snapshots da aplicacao.

    Returns:
        dict: List of application snapshots.
    """
    snapshots = await _client.get_snapshots()
    return {"status": "success", "data": snapshots}


TOOL_DEFINITIONS = [
    {
        "name": "get_snapshots",
        "description": "Get list of application snapshots from the EPM instance / Obter lista de snapshots da aplicacao",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]














