"""Personalization tools - onboarding checklist and user preferences."""

from typing import Any, Optional

from planning_agent.services.personalization_service import (
    get_personalization_service,
    PersonalizationService
)


async def get_personalization_status(user_id: str = "default") -> dict[str, Any]:
    """Get the current personalization/onboarding checklist status.

    Shows progress on configuring the Planning assistant with user preferences
    including application name, plan type, POV defaults, dimensions, and language.

    Args:
        user_id: User identifier (default: 'default')

    Returns:
        dict: Checklist status with items, progress, and completion state.
    """
    service = get_personalization_service()
    if not service:
        return {
            "status": "error",
            "error": "Personalization service not initialized"
        }

    try:
        status = service.get_status(user_id)
        return {
            "status": "success",
            "data": status.to_dict()
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def update_personalization_item(
    item_key: str,
    value: Any = None,
    is_done: bool = True,
    user_id: str = "default"
) -> dict[str, Any]:
    """Update a personalization checklist item.

    Valid item_key values:
    - app_name: Application name (e.g., 'PlanApp')
    - cube: Plan type/cube (e.g., 'FinPlan', 'OEP_FS')
    - pov_defaults: Default POV settings (dict with entity, scenario, years, etc.)
    - dimensions: Key dimensions configuration
    - language: Preferred language ('en', 'pt', etc.)
    - reporting: Reporting preferences

    Args:
        item_key: The checklist item key to update
        value: The value/response for the item
        is_done: Whether to mark the item as done (default: True)
        user_id: User identifier (default: 'default')

    Returns:
        dict: Success status and updated checklist state.
    """
    service = get_personalization_service()
    if not service:
        return {
            "status": "error",
            "error": "Personalization service not initialized"
        }

    try:
        success = service.update_item(
            item_key=item_key,
            is_done=is_done,
            value=value,
            user_id=user_id
        )

        if success:
            # Return updated status
            status = service.get_status(user_id)
            return {
                "status": "success",
                "message": f"Updated '{item_key}' successfully",
                "data": status.to_dict()
            }
        else:
            return {
                "status": "error",
                "error": f"Item '{item_key}' not found"
            }
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def set_personalization_preference(
    preference_key: str,
    preference_value: Any,
    user_id: str = "default"
) -> dict[str, Any]:
    """Set a user preference.

    Common preference keys:
    - app_name: Application name
    - default_plan_type: Default plan type for queries
    - pov_defaults: Default POV settings (dict)
    - language: Preferred language
    - date_format: Date format preference
    - number_format: Number format preference
    - export_format: Default export format (docx, xlsx, pdf)

    Args:
        preference_key: Preference identifier
        preference_value: Preference value (can be string, number, dict, list)
        user_id: User identifier (default: 'default')

    Returns:
        dict: Success status.
    """
    service = get_personalization_service()
    if not service:
        return {
            "status": "error",
            "error": "Personalization service not initialized"
        }

    try:
        success = service.set_preference(
            preference_key=preference_key,
            preference_value=preference_value,
            user_id=user_id
        )

        if success:
            return {
                "status": "success",
                "message": f"Preference '{preference_key}' set successfully",
                "data": {
                    "key": preference_key,
                    "value": preference_value
                }
            }
        else:
            return {
                "status": "error",
                "error": "Failed to set preference"
            }
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def get_personalization_preferences(user_id: str = "default") -> dict[str, Any]:
    """Get all user preferences.

    Args:
        user_id: User identifier (default: 'default')

    Returns:
        dict: All user preferences.
    """
    service = get_personalization_service()
    if not service:
        return {
            "status": "error",
            "error": "Personalization service not initialized"
        }

    try:
        preferences = service.get_all_preferences(user_id)
        return {
            "status": "success",
            "data": preferences
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


TOOL_DEFINITIONS = [
    {
        "name": "get_personalization_status",
        "description": "Get the current personalization/onboarding checklist status showing progress on configuring preferences / Obter status do checklist de personalizacao",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "User identifier (default: 'default')",
                },
            },
        },
    },
    {
        "name": "update_personalization_item",
        "description": "Update a personalization checklist item (app_name, cube, pov_defaults, dimensions, language, reporting) / Atualizar item do checklist de personalizacao",
        "inputSchema": {
            "type": "object",
            "properties": {
                "item_key": {
                    "type": "string",
                    "description": "The checklist item key (app_name, cube, pov_defaults, dimensions, language, reporting)",
                },
                "value": {
                    "description": "The value/response for the item",
                },
                "is_done": {
                    "type": "boolean",
                    "description": "Whether to mark the item as done (default: true)",
                },
                "user_id": {
                    "type": "string",
                    "description": "User identifier (default: 'default')",
                },
            },
            "required": ["item_key"],
        },
    },
    {
        "name": "set_personalization_preference",
        "description": "Set a user preference (app_name, default_plan_type, pov_defaults, language, etc.) / Definir preferencia do usuario",
        "inputSchema": {
            "type": "object",
            "properties": {
                "preference_key": {
                    "type": "string",
                    "description": "Preference identifier",
                },
                "preference_value": {
                    "description": "Preference value (string, number, dict, or list)",
                },
                "user_id": {
                    "type": "string",
                    "description": "User identifier (default: 'default')",
                },
            },
            "required": ["preference_key", "preference_value"],
        },
    },
    {
        "name": "get_personalization_preferences",
        "description": "Get all user preferences / Obter todas as preferencias do usuario",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "User identifier (default: 'default')",
                },
            },
        },
    },
]
