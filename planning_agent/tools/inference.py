"""Data Inference Tools for EPM Planning.

This module provides intelligent data discovery and inference:
1. smart_infer - Auto-discover valid intersections where data exists
2. infer_hierarchy - Understand member relationships
3. infer_valid_pov - Find working POV combinations
"""

from typing import Any, Optional, List, Dict

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


def _build_test_grid(entity: str, cost_center: str, region: str, account: str = "400000",
                     period: str = "Jan", years: str = "FY25", scenario: str = "Actual",
                     version: str = "Final", currency: str = "USD", future1: str = "Total Plan") -> dict:
    """Build a test grid to check if intersection has data."""
    return {
        "suppressMissingBlocks": True,
        "pov": {
            "members": [[entity], [scenario], [years], [version], [currency], [future1], [cost_center], [region]]
        },
        "columns": [{"dimensions": ["Period"], "members": [[period]]}],
        "rows": [{"dimensions": ["Account"], "members": [[account]]}]
    }


async def smart_infer(entity: str = "E501", scan_cost_centers: bool = True, scan_regions: bool = True,
                      scan_accounts: bool = False, test_account: str = "400000", max_tests: int = 50,
                      plan_type: str = "FinPlan") -> Dict[str, Any]:
    """Auto-discover valid intersections where data exists."""
    cache = get_metadata_cache()
    
    stats = cache.get_stats()
    if not stats.get("dimensions"):
        loaded = cache.load_all_dimensions()
        if not loaded:
            return {"status": "error", "error": "No metadata CSVs found. Export from Planning first."}
    
    candidates = {"cost_centers": [], "regions": []}
    
    if scan_cost_centers:
        leaves = cache.get_leaves("CostCenter")
        if leaves:
            priority = [l for l in leaves if l in ["CC1121", "CC1321", "CC2110", "CC2210", "CC2300", "CC2410"]]
            others = [l for l in leaves if l not in priority][:20]
            candidates["cost_centers"] = priority + others
        else:
            candidates["cost_centers"] = ["CC1121", "CC9999"]
    
    if scan_regions:
        leaves = cache.get_leaves("Region")
        if leaves:
            priority = [l for l in leaves if l in ["R131", "R001", "R002"]]
            others = [l for l in leaves if l not in priority][:10]
            candidates["regions"] = priority + others
        else:
            candidates["regions"] = ["R131"]
    
    if not candidates["regions"]:
        candidates["regions"] = ["R131"]
    if not candidates["cost_centers"]:
        candidates["cost_centers"] = ["CC1121"]
    
    test_combinations = []
    for cc in candidates["cost_centers"]:
        for region in candidates["regions"]:
            test_combinations.append((entity, cc, region))
            if len(test_combinations) >= max_tests:
                break
        if len(test_combinations) >= max_tests:
            break
    
    valid_intersections = []
    tested = 0
    errors = 0
    
    for entity_test, cc, region in test_combinations:
        try:
            grid = _build_test_grid(entity=entity_test, cost_center=cc, region=region, account=test_account)
            result = await _client.export_data_slice(_app_name, plan_type, grid)
            
            rows = result.get("rows", [])
            has_data = False
            value = None
            
            if rows:
                for row in rows:
                    data = row.get("data", [])
                    if data and any(d and d != "0" and d != "0.0" for d in data):
                        has_data = True
                        value = data[0] if data else None
                        break
            
            if has_data:
                valid_intersections.append({
                    "entity": entity_test, "cost_center": cc, "region": region,
                    "account": test_account, "sample_value": value, "has_data": True
                })
                cache.save_valid_intersection(entity_test, cc, region, test_account, True)
            
            tested += 1
        except Exception as e:
            errors += 1
            if errors > 10:
                break
    
    return {
        "status": "success", "entity": entity, "valid_intersections": valid_intersections,
        "tested_combinations": tested, "errors": errors,
        "recommendations": _generate_recommendations(valid_intersections)
    }


def _generate_recommendations(valid_intersections: List[Dict]) -> List[str]:
    """Generate recommendations based on discovered intersections."""
    if not valid_intersections:
        return ["No data found. Try different entity.", "Verify Period has data."]
    
    cost_centers = set(v["cost_center"] for v in valid_intersections)
    regions = set(v["region"] for v in valid_intersections)
    
    recommendations = []
    if len(cost_centers) == 1:
        recommendations.append(f"Data in CostCenter: {list(cost_centers)[0]}")
    else:
        recommendations.append(f"Data in {len(cost_centers)} CostCenters: {', '.join(list(cost_centers)[:5])}")
    
    if len(regions) == 1:
        recommendations.append(f"Data in Region: {list(regions)[0]}")
    
    recommendations.append("Use 'Total Plan' for Future1")
    return recommendations


async def infer_member(search_term: str, dimension: Optional[str] = None, limit: int = 5) -> Dict[str, Any]:
    """Infer/resolve a member name using semantic matching."""
    cache = get_metadata_cache()
    
    stats = cache.get_stats()
    if not stats.get("dimensions"):
        cache.load_all_dimensions()
    
    results = cache.semantic_search(search_term, dimension=dimension, limit=limit)
    
    if not results:
        return {"status": "not_found", "search_term": search_term, "dimension": dimension}
    
    return {
        "status": "success", "search_term": search_term, "matches": results,
        "best_match": results[0], "resolved_name": results[0]["member_name"]
    }


async def infer_hierarchy(dimension: str, member: str, direction: str = "both") -> Dict[str, Any]:
    """Infer hierarchical relationships for a member."""
    cache = get_metadata_cache()
    
    result = {"dimension": dimension, "member": member, "member_info": cache.get_member_info(dimension, member)}
    
    if direction in ("up", "both"):
        result["ancestors"] = cache.get_ancestors(dimension, member)
        result["path_to_root"] = [member] + result["ancestors"]
    
    if direction in ("down", "both"):
        result["children"] = [c["member_name"] for c in cache.get_children(dimension, member)]
        if result["children"]:
            result["is_parent"] = True
            result["child_count"] = len(result["children"])
    
    return result


async def infer_valid_pov(entity: str, account: Optional[str] = None, use_cache: bool = True) -> Dict[str, Any]:
    """Infer a valid POV combination for an entity."""
    cache = get_metadata_cache()
    
    if use_cache:
        cached = cache.get_valid_intersections(entity=entity)
        if cached:
            best = cached[0]
            return {
                "status": "success", "source": "cache",
                "pov": {
                    "entity": entity, "scenario": "Actual", "years": "FY25", "version": "Final",
                    "currency": "USD", "future1": "Total Plan", "cost_center": best["cost_center"],
                    "region": best["region"], "account": account or best.get("account", "400000"), "period": "YearTotal"
                },
                "confidence": "high"
            }
    
    defaults = {
        "E501": {"cost_center": "CC1121", "region": "R131"},
        "E502": {"cost_center": "CC2110", "region": "R131"},
        "E503": {"cost_center": "CC3210", "region": "R002"}
    }
    entity_defaults = defaults.get(entity, {"cost_center": "CC9999", "region": "R131"})
    
    return {
        "status": "success", "source": "defaults",
        "pov": {
            "entity": entity, "scenario": "Actual", "years": "FY25", "version": "Final",
            "currency": "USD", "future1": "Total Plan", "cost_center": entity_defaults["cost_center"],
            "region": entity_defaults["region"], "account": account or "400000", "period": "YearTotal"
        },
        "confidence": "medium", "note": "Run smart_infer to discover actual valid intersections."
    }


async def load_metadata_cache() -> Dict[str, Any]:
    """Load all dimension metadata into the semantic cache."""
    cache = get_metadata_cache()
    loaded = cache.load_all_dimensions()
    stats = cache.get_stats()
    return {"status": "success", "dimensions_loaded": loaded, "cache_stats": stats}


async def get_cache_stats() -> Dict[str, Any]:
    """Get current metadata cache statistics."""
    cache = get_metadata_cache()
    return {"status": "success", "stats": cache.get_stats()}


TOOL_DEFINITIONS = [
    {
        "name": "smart_infer",
        "description": "Auto-discover valid intersections where data exists. Scans dimension combinations to find working POV settings.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity": {"type": "string", "description": "Entity to scan (default: E501)", "default": "E501"},
                "scan_cost_centers": {"type": "boolean", "description": "Scan leaf cost centers", "default": True},
                "scan_regions": {"type": "boolean", "description": "Scan leaf regions", "default": True},
                "scan_accounts": {"type": "boolean", "description": "Also scan accounts (slower)", "default": False},
                "test_account": {"type": "string", "description": "Account for testing", "default": "400000"},
                "max_tests": {"type": "integer", "description": "Max API calls", "default": 50},
                "plan_type": {"type": "string", "description": "Plan type", "default": "FinPlan"}
            }
        }
    },
    {
        "name": "infer_member",
        "description": "Infer/resolve a member name using semantic matching. Finds members by alias, partial name, or fuzzy match.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "search_term": {"type": "string", "description": "Search input (alias, partial name, etc.)"},
                "dimension": {"type": "string", "description": "Optional dimension to search within"},
                "limit": {"type": "integer", "description": "Max results", "default": 5}
            },
            "required": ["search_term"]
        }
    },
    {
        "name": "infer_hierarchy",
        "description": "Infer hierarchical relationships for a member - ancestors, descendants, siblings.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dimension": {"type": "string", "description": "Dimension name"},
                "member": {"type": "string", "description": "Member name"},
                "direction": {"type": "string", "description": "'up', 'down', or 'both'", "default": "both", "enum": ["up", "down", "both"]}
            },
            "required": ["dimension", "member"]
        }
    },
    {
        "name": "infer_valid_pov",
        "description": "Infer a valid POV combination for an entity. Returns working dimension settings.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity": {"type": "string", "description": "Entity to find POV for"},
                "account": {"type": "string", "description": "Optional specific account"},
                "use_cache": {"type": "boolean", "description": "Use cached intersections", "default": True}
            },
            "required": ["entity"]
        }
    },
    {
        "name": "load_metadata_cache",
        "description": "Load all dimension metadata into the semantic cache from CSV files.",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_cache_stats",
        "description": "Get metadata cache statistics - loaded dimensions, member counts.",
        "inputSchema": {"type": "object", "properties": {}}
    }
]
