"""Dimension tools - get_dimensions, get_members, get_member."""

from typing import Any, Optional

from planning_agent.client.planning_client import PlanningClient

_client: PlanningClient = None
_app_name: str = None


def set_client(client: PlanningClient):
    global _client
    _client = client


def set_app_name(app_name: str):
    global _app_name
    _app_name = app_name


async def get_dimensions() -> dict[str, Any]:
    """Get list of dimensions in the application / Obter lista de dimensoes na aplicacao.

    Returns:
        dict: List of dimensions with their types.
    """
    dimensions = await _client.get_dimensions(_app_name)
    return {"status": "success", "data": dimensions}


async def get_members(dimension_name: str) -> dict[str, Any]:
    """Get members of a specific dimension / Obter membros de uma dimensao especifica.

    Args:
        dimension_name: The name of the dimension.

    Returns:
        dict: List of dimension members.
    """
    members = await _client.get_members(_app_name, dimension_name)
    return {"status": "success", "data": members}


async def get_member(
    dimension_name: str,
    member_name: str,
    expansion: Optional[str] = None
) -> dict[str, Any]:
    """Get a specific member by name from a dimension, with optional expansion to get children or descendants / Obter um membro especifico.

    Args:
        dimension_name: The name of the dimension.
        member_name: The name of the member to retrieve.
        expansion: Optional expansion type to get related members (e.g., 'children', 'descendants').

    Returns:
        dict: Member details with optional children/descendants.
    """
    member = await _client.get_member(_app_name, dimension_name, member_name, expansion)
    return {"status": "success", "data": member}


TOOL_DEFINITIONS = [
    {
        "name": "get_dimensions",
        "description": "Get list of dimensions in the application / Obter lista de dimensoes na aplicacao",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_members",
        "description": "Get members of a specific dimension / Obter membros de uma dimensao especifica",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dimension_name": {
                    "type": "string",
                    "description": "The name of the dimension",
                },
            },
            "required": ["dimension_name"],
        },
    },
    {
        "name": "get_member",
        "description": "Get a specific member by name from a dimension, with optional expansion / Obter um membro especifico",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dimension_name": {
                    "type": "string",
                    "description": "The name of the dimension",
                },
                "member_name": {
                    "type": "string",
                    "description": "The name of the member to retrieve",
                },
                "expansion": {
                    "type": "string",
                    "description": "Optional expansion type (e.g., 'children', 'descendants')",
                },
            },
            "required": ["dimension_name", "member_name"],
        },
    },
]


