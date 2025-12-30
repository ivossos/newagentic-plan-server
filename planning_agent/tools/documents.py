"""Document tools - get_documents."""

from typing import Any

from planning_agent.client.planning_client import PlanningClient

_client: PlanningClient = None
_app_name: str = None


def set_client(client: PlanningClient):
    global _client
    _client = client


def set_app_name(app_name: str):
    global _app_name
    _app_name = app_name


async def get_documents() -> dict[str, Any]:
    """Get list of library documents in a Planning application / Obter lista de documentos da biblioteca.

    Returns:
        dict: List of documents in the library.
    """
    documents = await _client.get_documents(_app_name)
    return {"status": "success", "data": documents}


TOOL_DEFINITIONS = [
    {
        "name": "get_documents",
        "description": "Get list of library documents in a Planning application / Obter lista de documentos da biblioteca",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


