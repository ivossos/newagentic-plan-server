"""Valid Intersections Tools for EPM Planning.

This module provides tools for managing valid intersections in Oracle EPM:
1. Export/Import valid intersection groups via REST API
2. Validate member combinations before data operations
3. Discover valid intersections by testing data availability
4. Cache and manage valid intersection rules locally

Valid intersections in EPM prevent data entry for invalid dimension member
combinations as defined in valid intersection groups.
"""

import json
from typing import Any, Optional, List, Dict
from datetime import datetime

from planning_agent.client.planning_client import PlanningClient
from planning_agent.utils.metadata_cache import get_metadata_cache, MetadataCache

_client: PlanningClient = None
_app_name: str = None


def set_client(client: PlanningClient):
    global _client
    _client = client


def set_app_name(app_name: str):
    global _app_name
    _app_name = app_name


# ========== REST API Operations ==========

async def export_valid_intersections(
    file_name: str = "ValidIntersections.zip",
    names: Optional[str] = None
) -> Dict[str, Any]:
    """Export valid intersection groups to a ZIP file in the Outbox.

    This exports the valid intersection definitions from the EPM application.
    The output file can be downloaded via the Download REST API.

    Args:
        file_name: Output ZIP file name (default: ValidIntersections.zip).
        names: Comma-separated list of valid intersection names to export.
               If not specified, exports all valid intersections.

    Returns:
        dict: Job submission result with jobId for tracking.

    Example:
        # Export all valid intersections
        result = await export_valid_intersections()

        # Export specific intersections
        result = await export_valid_intersections(
            names="VIAccountPeriod,VIEntityRegion"
        )
    """
    result = await _client.export_valid_intersections(_app_name, file_name, names)
    return {
        "status": "success",
        "job": result,
        "note": f"Valid intersections will be exported to Outbox/{file_name}. Use get_job_status to track completion."
    }


async def import_valid_intersections(
    file_name: str,
    error_file: Optional[str] = None
) -> Dict[str, Any]:
    """Import valid intersection groups from a ZIP file in the Inbox.

    The ZIP file must contain an Excel file with valid intersection definitions
    in the correct format (two worksheets: Groups and Rules).

    Args:
        file_name: ZIP file name in Inbox containing valid intersection definitions.
        error_file: Optional error log file name for rejected records.

    Returns:
        dict: Job submission result with jobId for tracking.

    Example:
        result = await import_valid_intersections("ImportVIRecords.zip")
    """
    result = await _client.import_valid_intersections(_app_name, file_name, error_file)
    return {
        "status": "success",
        "job": result,
        "note": "Check job status for completion. Rejected records will be in Outbox."
    }


async def get_valid_intersection_groups() -> Dict[str, Any]:
    """Get valid intersection groups metadata from the application.

    Returns:
        dict: List of valid intersection groups with their dimensions.
    """
    result = await _client.get_valid_intersection_groups(_app_name)
    return {"status": "success", "groups": result.get("items", []), "note": result.get("note")}


# ========== Validation Functions ==========

async def validate_intersection(
    members: Dict[str, str],
    use_cache: bool = True,
    test_with_api: bool = False,
    plan_type: str = "FinPlan"
) -> Dict[str, Any]:
    """Validate if a dimension member combination is valid.

    Checks whether the given combination of dimension members constitutes
    a valid intersection that can accept data.

    Args:
        members: Dictionary mapping dimension names to member names.
                 Example: {"Entity": "E501", "CostCenter": "CC1121", "Region": "R131"}
        use_cache: Whether to check the local cache first (default: True).
        test_with_api: If True and cache miss, test by attempting data retrieval.
        plan_type: Plan type for API testing (default: FinPlan).

    Returns:
        dict: Validation result with is_valid flag and details.

    Example:
        result = await validate_intersection({
            "Entity": "E501",
            "CostCenter": "CC1121",
            "Region": "R131"
        })
    """
    cache = get_metadata_cache()

    # First, verify all members exist in their dimensions
    member_validation = {}
    all_members_valid = True

    for dimension, member in members.items():
        info = cache.get_member_info(dimension, member)
        if info:
            member_validation[dimension] = {
                "member": member,
                "exists": True,
                "is_leaf": info.get("is_leaf", False)
            }
        else:
            # Try semantic search
            resolved = cache.resolve_member(member, dimension)
            if resolved:
                member_validation[dimension] = {
                    "member": member,
                    "exists": True,
                    "resolved_to": resolved,
                    "is_leaf": cache.get_member_info(dimension, resolved).get("is_leaf", False)
                }
            else:
                member_validation[dimension] = {
                    "member": member,
                    "exists": False
                }
                all_members_valid = False

    if not all_members_valid:
        return {
            "status": "invalid",
            "is_valid": False,
            "reason": "One or more members do not exist",
            "member_validation": member_validation
        }

    # Check cache for known valid intersection
    if use_cache:
        entity = members.get("Entity")
        cost_center = members.get("CostCenter")
        region = members.get("Region")

        if entity and cost_center and region:
            cached = cache.get_valid_intersections(
                entity=entity,
                cost_center=cost_center,
                region=region
            )
            if cached:
                return {
                    "status": "valid",
                    "is_valid": True,
                    "source": "cache",
                    "member_validation": member_validation,
                    "cached_intersection": cached[0]
                }

    # Optionally test with API
    if test_with_api:
        try:
            grid = _build_validation_grid(members)
            result = await _client.export_data_slice(_app_name, plan_type, grid)

            has_data = False
            if result.get("rows"):
                for row in result["rows"]:
                    if row.get("data") and any(d and d != "0" for d in row["data"]):
                        has_data = True
                        break

            # Cache the result
            if has_data and "Entity" in members and "CostCenter" in members and "Region" in members:
                cache.save_valid_intersection(
                    entity=members["Entity"],
                    cost_center=members["CostCenter"],
                    region=members["Region"],
                    account=members.get("Account"),
                    has_data=True
                )

            return {
                "status": "valid" if has_data else "no_data",
                "is_valid": True,  # Intersection is valid even if no data
                "has_data": has_data,
                "source": "api_test",
                "member_validation": member_validation
            }
        except Exception as e:
            return {
                "status": "error",
                "is_valid": False,
                "reason": f"API test failed: {str(e)}",
                "member_validation": member_validation
            }

    # Without API test, assume valid if all members exist
    return {
        "status": "unknown",
        "is_valid": True,
        "source": "member_existence_only",
        "member_validation": member_validation,
        "note": "Set test_with_api=True to verify against actual data"
    }


def _build_validation_grid(members: Dict[str, str]) -> Dict[str, Any]:
    """Build a grid definition for validation testing."""
    # Default values for required dimensions
    defaults = {
        "Entity": "E501",
        "Scenario": "Actual",
        "Years": "FY25",
        "Version": "Final",
        "Currency": "USD",
        "Future1": "Total Plan",
        "CostCenter": "CC9999",
        "Region": "R131",
        "Period": "YearTotal",
        "Account": "400000"
    }

    # Merge provided members with defaults
    merged = {**defaults, **members}

    return {
        "suppressMissingBlocks": True,
        "pov": {
            "members": [
                [merged["Entity"]],
                [merged["Scenario"]],
                [merged["Years"]],
                [merged["Version"]],
                [merged["Currency"]],
                [merged["Future1"]],
                [merged["CostCenter"]],
                [merged["Region"]]
            ]
        },
        "columns": [{"dimensions": ["Period"], "members": [[merged["Period"]]]}],
        "rows": [{"dimensions": ["Account"], "members": [[merged["Account"]]]}]
    }


async def validate_pov(
    entity: str,
    cost_center: str,
    region: str,
    account: Optional[str] = None,
    test_with_api: bool = False
) -> Dict[str, Any]:
    """Simplified validation for common POV combination.

    Args:
        entity: Entity member name.
        cost_center: CostCenter member name.
        region: Region member name.
        account: Optional Account member name.
        test_with_api: Whether to test against actual data.

    Returns:
        dict: Validation result.
    """
    members = {
        "Entity": entity,
        "CostCenter": cost_center,
        "Region": region
    }
    if account:
        members["Account"] = account

    return await validate_intersection(members, test_with_api=test_with_api)


# ========== Discovery Functions ==========

async def discover_valid_intersections(
    entity: str,
    dimensions_to_scan: Optional[List[str]] = None,
    max_combinations: int = 100,
    plan_type: str = "FinPlan"
) -> Dict[str, Any]:
    """Discover valid intersections by systematically testing combinations.

    Scans dimension member combinations to find which intersections have data.
    Results are cached for future use.

    Args:
        entity: Entity to scan for.
        dimensions_to_scan: List of dimensions to scan (default: CostCenter, Region).
        max_combinations: Maximum number of API calls to make.
        plan_type: Plan type for data retrieval.

    Returns:
        dict: Discovery results with valid intersections found.
    """
    cache = get_metadata_cache()

    # Ensure metadata is loaded
    stats = cache.get_stats()
    if not stats.get("dimensions"):
        cache.load_all_dimensions()

    if dimensions_to_scan is None:
        dimensions_to_scan = ["CostCenter", "Region"]

    # Get leaf members for each dimension
    dimension_members = {}
    for dim in dimensions_to_scan:
        leaves = cache.get_leaves(dim)
        if leaves:
            # Limit to 20 per dimension to avoid explosion
            dimension_members[dim] = leaves[:20]
        else:
            dimension_members[dim] = []

    # Generate combinations
    combinations = []
    if "CostCenter" in dimension_members and "Region" in dimension_members:
        for cc in dimension_members.get("CostCenter", ["CC9999"]):
            for region in dimension_members.get("Region", ["R131"]):
                combinations.append({"Entity": entity, "CostCenter": cc, "Region": region})
                if len(combinations) >= max_combinations:
                    break
            if len(combinations) >= max_combinations:
                break

    # Test each combination
    valid_found = []
    invalid_found = []
    errors = 0

    for combo in combinations:
        try:
            grid = _build_validation_grid(combo)
            result = await _client.export_data_slice(_app_name, plan_type, grid)

            has_data = False
            sample_value = None
            if result.get("rows"):
                for row in result["rows"]:
                    if row.get("data") and any(d and d != "0" and d != "0.0" for d in row["data"]):
                        has_data = True
                        sample_value = row["data"][0]
                        break

            if has_data:
                valid_found.append({**combo, "has_data": True, "sample_value": sample_value})
                cache.save_valid_intersection(
                    entity=combo["Entity"],
                    cost_center=combo["CostCenter"],
                    region=combo["Region"],
                    has_data=True
                )
            else:
                invalid_found.append({**combo, "has_data": False})

        except Exception as e:
            errors += 1
            if errors > 10:
                break

    return {
        "status": "success",
        "entity": entity,
        "combinations_tested": len(combinations),
        "valid_intersections": valid_found,
        "invalid_intersections": invalid_found[:10],  # Limit for readability
        "errors": errors,
        "summary": {
            "valid_count": len(valid_found),
            "invalid_count": len(invalid_found),
            "valid_cost_centers": list(set(v["CostCenter"] for v in valid_found)),
            "valid_regions": list(set(v["Region"] for v in valid_found))
        }
    }


async def get_cached_valid_intersections(
    entity: Optional[str] = None,
    cost_center: Optional[str] = None,
    region: Optional[str] = None
) -> Dict[str, Any]:
    """Get cached valid intersections from local database.

    Args:
        entity: Filter by entity.
        cost_center: Filter by cost center.
        region: Filter by region.

    Returns:
        dict: List of cached valid intersections.
    """
    cache = get_metadata_cache()
    intersections = cache.get_valid_intersections(
        entity=entity,
        cost_center=cost_center,
        region=region
    )

    return {
        "status": "success",
        "count": len(intersections),
        "intersections": intersections,
        "filters_applied": {
            "entity": entity,
            "cost_center": cost_center,
            "region": region
        }
    }


async def suggest_valid_pov(
    entity: str,
    account: Optional[str] = None,
    prefer_cached: bool = True
) -> Dict[str, Any]:
    """Suggest a valid POV combination for an entity.

    Uses cached valid intersections to suggest working dimension values.

    Args:
        entity: Entity to find valid POV for.
        account: Optional account to include in suggestion.
        prefer_cached: Whether to prefer cached intersections.

    Returns:
        dict: Suggested POV with all dimension values.
    """
    cache = get_metadata_cache()

    # Try to find cached valid intersections
    if prefer_cached:
        cached = cache.get_valid_intersections(entity=entity)
        if cached:
            best = cached[0]
            return {
                "status": "success",
                "source": "cache",
                "confidence": "high",
                "pov": {
                    "entity": entity,
                    "scenario": "Actual",
                    "years": "FY25",
                    "period": "YearTotal",
                    "version": "Final",
                    "currency": "USD",
                    "future1": "Total Plan",
                    "cost_center": best["cost_center"],
                    "region": best["region"],
                    "account": account or best.get("account") or "400000"
                },
                "note": "Based on previously discovered valid intersection"
            }

    # Fallback to defaults
    entity_defaults = {
        "E501": {"cost_center": "CC1121", "region": "R131"},
        "E502": {"cost_center": "CC2110", "region": "R131"},
        "E503": {"cost_center": "CC3210", "region": "R002"}
    }

    defaults = entity_defaults.get(entity, {"cost_center": "CC9999", "region": "R131"})

    return {
        "status": "success",
        "source": "defaults",
        "confidence": "medium",
        "pov": {
            "entity": entity,
            "scenario": "Actual",
            "years": "FY25",
            "period": "YearTotal",
            "version": "Final",
            "currency": "USD",
            "future1": "Total Plan",
            "cost_center": defaults["cost_center"],
            "region": defaults["region"],
            "account": account or "400000"
        },
        "note": "Using default values. Run discover_valid_intersections to find actual valid combinations."
    }


# ========== Tool Definitions ==========

TOOL_DEFINITIONS = [
    {
        "name": "export_valid_intersections",
        "description": "Export valid intersection groups from EPM to a ZIP file. The file is placed in Outbox.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_name": {
                    "type": "string",
                    "description": "Output ZIP file name (default: ValidIntersections.zip)",
                    "default": "ValidIntersections.zip"
                },
                "names": {
                    "type": "string",
                    "description": "Comma-separated list of valid intersection names to export. Leave empty for all."
                }
            }
        }
    },
    {
        "name": "import_valid_intersections",
        "description": "Import valid intersection groups from a ZIP file in Inbox into EPM application.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_name": {
                    "type": "string",
                    "description": "ZIP file name in Inbox containing valid intersection definitions"
                },
                "error_file": {
                    "type": "string",
                    "description": "Optional error log file name for rejected records"
                }
            },
            "required": ["file_name"]
        }
    },
    {
        "name": "get_valid_intersection_groups",
        "description": "Get valid intersection groups metadata from the EPM application.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "validate_intersection",
        "description": "Validate if a dimension member combination is a valid intersection. Checks member existence and optionally tests against actual data.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "members": {
                    "type": "object",
                    "description": "Dictionary mapping dimension names to member names. E.g., {\"Entity\": \"E501\", \"CostCenter\": \"CC1121\"}"
                },
                "use_cache": {
                    "type": "boolean",
                    "description": "Check local cache first (default: true)",
                    "default": True
                },
                "test_with_api": {
                    "type": "boolean",
                    "description": "Test against actual data via API (default: false)",
                    "default": False
                },
                "plan_type": {
                    "type": "string",
                    "description": "Plan type for API testing (default: FinPlan)",
                    "default": "FinPlan"
                }
            },
            "required": ["members"]
        }
    },
    {
        "name": "validate_pov",
        "description": "Simplified validation for Entity-CostCenter-Region combination.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity": {"type": "string", "description": "Entity member name"},
                "cost_center": {"type": "string", "description": "CostCenter member name"},
                "region": {"type": "string", "description": "Region member name"},
                "account": {"type": "string", "description": "Optional Account member name"},
                "test_with_api": {
                    "type": "boolean",
                    "description": "Test against actual data (default: false)",
                    "default": False
                }
            },
            "required": ["entity", "cost_center", "region"]
        }
    },
    {
        "name": "discover_valid_intersections",
        "description": "Discover valid intersections by systematically testing dimension member combinations. Results are cached.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity": {"type": "string", "description": "Entity to scan for"},
                "dimensions_to_scan": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Dimensions to scan (default: CostCenter, Region)"
                },
                "max_combinations": {
                    "type": "integer",
                    "description": "Maximum API calls to make (default: 100)",
                    "default": 100
                },
                "plan_type": {
                    "type": "string",
                    "description": "Plan type (default: FinPlan)",
                    "default": "FinPlan"
                }
            },
            "required": ["entity"]
        }
    },
    {
        "name": "get_cached_valid_intersections",
        "description": "Get cached valid intersections from local database with optional filters.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity": {"type": "string", "description": "Filter by entity"},
                "cost_center": {"type": "string", "description": "Filter by cost center"},
                "region": {"type": "string", "description": "Filter by region"}
            }
        }
    },
    {
        "name": "suggest_valid_pov",
        "description": "Suggest a valid POV combination for an entity using cached intersections or defaults.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity": {"type": "string", "description": "Entity to find valid POV for"},
                "account": {"type": "string", "description": "Optional account to include"},
                "prefer_cached": {
                    "type": "boolean",
                    "description": "Prefer cached intersections (default: true)",
                    "default": True
                }
            },
            "required": ["entity"]
        }
    }
]
