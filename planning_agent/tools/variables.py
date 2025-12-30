"""Substitution variable tools - get_substitution_variables, set_substitution_variable."""

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


async def get_substitution_variables() -> dict[str, Any]:
    """Get all substitution variables in a Planning application / Obter todas as variaveis de substituicao.

    Returns:
        dict: List of substitution variables with their values.
    """
    variables = await _client.get_substitution_variables(_app_name)
    return {"status": "success", "data": variables}


async def set_substitution_variable(
    variable_name: str,
    value: str,
    plan_type: Optional[str] = None
) -> dict[str, Any]:
    """Set a substitution variable value / Definir valor de variavel de substituicao.

    Args:
        variable_name: Name of the variable to set.
        value: Value to set.
        plan_type: Optional plan type for the variable.

    Returns:
        dict: Updated variable information.
    """
    result = await _client.set_substitution_variable(_app_name, variable_name, value, plan_type)
    return {"status": "success", "data": result}


TOOL_DEFINITIONS = [
    {
        "name": "get_substitution_variables",
        "description": "Get all substitution variables in a Planning application / Obter todas as variaveis de substituicao",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "set_substitution_variable",
        "description": "Set a substitution variable value / Definir valor de variavel de substituicao",
        "inputSchema": {
            "type": "object",
            "properties": {
                "variable_name": {
                    "type": "string",
                    "description": "Name of the variable to set",
                },
                "value": {
                    "type": "string",
                    "description": "Value to set",
                },
                "plan_type": {
                    "type": "string",
                    "description": "Optional plan type for the variable",
                },
            },
            "required": ["variable_name", "value"],
        },
    },
]


