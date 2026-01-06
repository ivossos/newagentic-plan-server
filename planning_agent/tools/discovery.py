"""Discovery tools - Dynamic data discovery for custom Planning applications.

This module provides tools to discover and explore unknown Planning application structures,
enabling data retrieval without prior knowledge of dimension configurations.
"""

from typing import Any, Optional, List, Dict
from dataclasses import dataclass, field
from pathlib import Path
import csv

from planning_agent.client.planning_client import PlanningClient

# Path to metadata CSV files
DATA_DIR = Path(__file__).parent.parent.parent / "data"

# Global state
_client: Optional[PlanningClient] = None
_app_name: Optional[str] = None

# Cache for discovered structures
_discovered_structure: Dict[str, Any] = {}

# Configuration constants
MAX_SAMPLE_MEMBERS = 10
MAX_CHILDREN_DISPLAYED = 20
MAX_ROOTS_DISPLAYED = 10
DENSE_TYPE_INDICATORS = ["Account", "Period", "Time", "Currency"]


def set_client(client: PlanningClient):
    global _client
    _client = client


def set_app_name(app_name: str):
    global _app_name
    _app_name = app_name


def _validate_client() -> Optional[Dict[str, Any]]:
    """Validate that client and app_name are initialized.

    Returns:
        None if valid, error dict if invalid.
    """
    if _client is None:
        return {"status": "error", "error": "Client not initialized. Call set_client() first."}
    if _app_name is None:
        return {"status": "error", "error": "App name not set. Call set_app_name() first."}
    return None


def _load_members_from_csv(dimension_name: str) -> Optional[List[Dict[str, str]]]:
    """Load dimension members from exported CSV metadata files.

    Args:
        dimension_name: The dimension name to look up.

    Returns:
        List of member dicts with name, parent, alias, or None if not found.
    """
    csv_path = DATA_DIR / f"ExportedMetadata_{dimension_name}.csv"
    if not csv_path.exists():
        return None

    members = []
    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header:
                return None

            # Find column indices (handle varying column names)
            name_idx = 0  # First column is always the member name
            parent_idx = 1 if len(header) > 1 else None
            alias_idx = None
            for i, col in enumerate(header):
                if 'alias' in col.lower() and 'default' in col.lower():
                    alias_idx = i
                    break
                elif 'alias' in col.lower() and alias_idx is None:
                    alias_idx = i

            for row in reader:
                if not row or not row[0].strip():
                    continue
                member = {
                    "name": row[name_idx].strip(),
                    "parent": row[parent_idx].strip() if parent_idx and len(row) > parent_idx else "",
                    "alias": row[alias_idx].strip() if alias_idx and len(row) > alias_idx else ""
                }
                members.append(member)

        return members
    except Exception:
        return None


@dataclass
class DimensionInfo:
    """Information about a discovered dimension."""
    name: str
    dim_type: str
    is_dense: bool = False
    member_count: int = 0
    root_members: List[str] = field(default_factory=list)
    sample_members: List[str] = field(default_factory=list)


@dataclass
class AppStructure:
    """Complete structure of a discovered application."""
    app_name: str
    plan_types: List[str] = field(default_factory=list)
    dimensions: List[DimensionInfo] = field(default_factory=list)
    dense_dimensions: List[str] = field(default_factory=list)
    sparse_dimensions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "app_name": self.app_name,
            "plan_types": self.plan_types,
            "dimensions": [
                {
                    "name": d.name,
                    "type": d.dim_type,
                    "is_dense": d.is_dense,
                    "member_count": d.member_count,
                    "root_members": d.root_members,
                    "sample_members": d.sample_members
                }
                for d in self.dimensions
            ],
            "dense_dimensions": self.dense_dimensions,
            "sparse_dimensions": self.sparse_dimensions
        }


async def discover_app_structure() -> Dict[str, Any]:
    """Discover the complete structure of a Planning application.

    This is the starting point for exploring any custom/freeform app.
    Returns all dimensions, their types, plan types, and basic hierarchy info.

    Returns:
        dict: Complete application structure with dimensions and plan types.
    """
    global _discovered_structure

    validation_error = _validate_client()
    if validation_error:
        return validation_error

    try:
        # Step 1: Get application info
        apps_response = await _client.get_applications()
        apps = apps_response.get("items", [])

        current_app = None
        plan_types = []

        for app in apps:
            if app.get("name") == _app_name:
                current_app = app
                # Extract plan types if available
                plan_types = app.get("planTypes", [])
                if not plan_types:
                    # Try common plan type names
                    plan_types = ["Plan1", "Plan2", "Plan3"]
                break

        # Step 2: Get dimensions
        dims_response = await _client.get_dimensions(_app_name)
        dims = dims_response.get("items", [])

        structure = AppStructure(
            app_name=_app_name,
            plan_types=plan_types
        )

        # Step 3: Analyze each dimension
        for dim in dims:
            dim_name = dim.get("name", "")
            dim_type = dim.get("type", "Unknown")

            # Determine if dense or sparse based on type
            is_dense = any(dt.lower() in dim_type.lower() for dt in DENSE_TYPE_INDICATORS)

            dim_info = DimensionInfo(
                name=dim_name,
                dim_type=dim_type,
                is_dense=is_dense
            )

            # Try to get sample members (API first, then CSV fallback)
            members = []
            try:
                members_response = await _client.get_members(_app_name, dim_name)
                members = members_response.get("items", [])
            except Exception:
                pass

            # If API returned no members, try CSV fallback
            if not members:
                csv_members = _load_members_from_csv(dim_name)
                if csv_members:
                    members = csv_members

            if members:
                dim_info.member_count = len(members)

                # Get root/top-level members and samples
                for m in members[:MAX_SAMPLE_MEMBERS]:
                    member_name = m.get("name", m) if isinstance(m, dict) else str(m)
                    dim_info.sample_members.append(member_name)

                    # Identify root members (no parent or parent is dimension name)
                    parent = m.get("parent", "") if isinstance(m, dict) else ""
                    if not parent or parent == dim_name:
                        dim_info.root_members.append(member_name)
            else:
                # Neither API nor CSV available
                dim_info.sample_members = ["(no data)"]

            structure.dimensions.append(dim_info)

            if is_dense:
                structure.dense_dimensions.append(dim_name)
            else:
                structure.sparse_dimensions.append(dim_name)

        # Cache the discovered structure
        _discovered_structure = structure.to_dict()

        return {
            "status": "success",
            "data": structure.to_dict(),
            "summary": {
                "app_name": _app_name,
                "total_dimensions": len(structure.dimensions),
                "dense_count": len(structure.dense_dimensions),
                "sparse_count": len(structure.sparse_dimensions),
                "plan_types": structure.plan_types,
                "dimension_names": [d.name for d in structure.dimensions]
            }
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def explore_dimension(
    dimension_name: str,
    parent_member: Optional[str] = None,
    depth: int = 2,
    include_aliases: bool = True
) -> Dict[str, Any]:
    """Explore a dimension's hierarchy starting from a parent member.

    Args:
        dimension_name: The name of the dimension to explore.
        parent_member: Starting member (None = start from root).
        depth: How deep to explore (default: 2 levels).
        include_aliases: Include member aliases if available.

    Returns:
        dict: Hierarchical structure of the dimension.
    """
    validation_error = _validate_client()
    if validation_error:
        return validation_error

    try:
        if parent_member:
            # Get specific member with descendants
            member_response = await _client.get_member(
                _app_name,
                dimension_name,
                parent_member,
                expansion="descendants" if depth > 1 else "children"
            )

            return {
                "status": "success",
                "data": {
                    "dimension": dimension_name,
                    "starting_member": parent_member,
                    "hierarchy": member_response
                }
            }
        else:
            # Get all members and build hierarchy
            members_response = await _client.get_members(_app_name, dimension_name)
            members = members_response.get("items", [])

            # Build hierarchy from flat list
            hierarchy = _build_hierarchy(members, depth)

            return {
                "status": "success",
                "data": {
                    "dimension": dimension_name,
                    "total_members": len(members),
                    "hierarchy": hierarchy,
                    "all_members": [
                        _extract_member_info(m, include_aliases)
                        for m in members
                    ]
                }
            }

    except Exception as e:
        return {"status": "error", "error": str(e)}


def _extract_member_info(member: Any, include_aliases: bool) -> Dict[str, Any]:
    """Extract member information from API response."""
    if isinstance(member, dict):
        info = {
            "name": member.get("name", ""),
            "parent": member.get("parent", ""),
        }
        if include_aliases:
            info["alias"] = member.get("alias", member.get("description", ""))
        return info
    return {"name": str(member), "parent": "", "alias": ""}


def _build_hierarchy(members: List[Any], max_depth: int) -> Dict[str, Any]:
    """Build hierarchy tree from flat member list."""
    # Create lookup
    member_dict = {}
    for m in members:
        if isinstance(m, dict):
            name = m.get("name", "")
            parent = m.get("parent", "")
            member_dict[name] = {"parent": parent, "children": []}
        else:
            member_dict[str(m)] = {"parent": "", "children": []}

    # Build parent-child relationships
    roots = []
    for name, info in member_dict.items():
        parent = info["parent"]
        if parent and parent in member_dict:
            member_dict[parent]["children"].append(name)
        elif not parent:
            roots.append(name)

    # Build tree structure (limited depth)
    def build_tree(name: str, current_depth: int) -> Dict[str, Any]:
        if current_depth >= max_depth:
            return {"name": name, "children": "..."}

        children = member_dict.get(name, {}).get("children", [])
        return {
            "name": name,
            "children": [
                build_tree(c, current_depth + 1)
                for c in children[:MAX_CHILDREN_DISPLAYED]
            ]
        }

    return {
        "roots": [build_tree(r, 0) for r in roots[:MAX_ROOTS_DISPLAYED]],
        "total_roots": len(roots)
    }


async def find_members(
    search_term: str,
    dimension_name: Optional[str] = None,
    search_aliases: bool = True,
    limit: int = 50
) -> Dict[str, Any]:
    """Search for members across dimensions by name or alias pattern.

    NOTE: EPM Planning API does not support server-side member search,
    so we fetch all members and filter client-side.

    Args:
        search_term: Text to search for (case-insensitive, partial match).
        dimension_name: Specific dimension to search (None = all dimensions).
        search_aliases: Also search in aliases/descriptions.
        limit: Maximum results to return.

    Returns:
        dict: Matching members organized by dimension.
    """
    validation_error = _validate_client()
    if validation_error:
        return validation_error

    results = {}
    search_lower = search_term.lower()

    try:
        # Determine which dimensions to search
        if dimension_name:
            dimensions_to_search = [dimension_name]
        else:
            # Get all dimensions
            dims_response = await _client.get_dimensions(_app_name)
            dimensions_to_search = [
                d.get("name", d) if isinstance(d, dict) else str(d)
                for d in dims_response.get("items", [])
            ]

        total_found = 0

        for dim in dimensions_to_search:
            if total_found >= limit:
                break

            try:
                members_response = await _client.get_members(_app_name, dim)
                members = members_response.get("items", [])

                matches = []
                for m in members:
                    if total_found >= limit:
                        break

                    name = m.get("name", str(m)) if isinstance(m, dict) else str(m)
                    alias = m.get("alias", "") if isinstance(m, dict) else ""
                    desc = m.get("description", "") if isinstance(m, dict) else ""

                    # Check for match
                    name_match = search_lower in name.lower()
                    alias_match = search_aliases and (
                        search_lower in alias.lower() or
                        search_lower in desc.lower()
                    )

                    if name_match or alias_match:
                        matches.append({
                            "name": name,
                            "alias": alias or desc,
                            "parent": m.get("parent", "") if isinstance(m, dict) else "",
                            "match_type": "name" if name_match else "alias"
                        })
                        total_found += 1

                if matches:
                    results[dim] = matches

            except Exception:
                # Skip dimensions we can't access
                continue

        return {
            "status": "success",
            "data": {
                "search_term": search_term,
                "total_found": total_found,
                "results_by_dimension": results
            }
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def build_dynamic_grid(
    row_dimension: str,
    row_members: List[str],
    column_dimension: str,
    column_members: List[str],
    pov_selections: Dict[str, str]
) -> Dict[str, Any]:
    """Build a grid definition dynamically based on discovered structure.

    This tool auto-constructs the correct grid format for any custom app
    based on its actual dimension configuration.

    Args:
        row_dimension: Dimension to place on rows (e.g., "Account").
        row_members: Members for the row dimension.
        column_dimension: Dimension to place on columns (e.g., "Period").
        column_members: Members for the column dimension.
        pov_selections: Dict of {dimension_name: member_name} for POV dimensions.

    Returns:
        dict: Ready-to-use grid definition.
    """
    global _discovered_structure

    validation_error = _validate_client()
    if validation_error:
        return validation_error

    try:
        # Get structure if not cached
        if not _discovered_structure:
            await discover_app_structure()

        all_dims = [d["name"] for d in _discovered_structure.get("dimensions", [])]

        # Validate dimensions exist
        for dim in [row_dimension, column_dimension] + list(pov_selections.keys()):
            if dim not in all_dims:
                return {
                    "status": "error",
                    "error": f"Dimension '{dim}' not found. Available: {all_dims}"
                }

        # Build POV members list (ordered by discovery order, excluding row/column dims)
        pov_members = []
        pov_dimensions = []

        for dim_info in _discovered_structure.get("dimensions", []):
            dim_name = dim_info["name"]
            if dim_name == row_dimension or dim_name == column_dimension:
                continue

            if dim_name in pov_selections:
                pov_members.append([pov_selections[dim_name]])
            else:
                # Use first sample member as default
                samples = dim_info.get("sample_members", [])
                default = samples[0] if samples else dim_info.get("root_members", [""])[0]
                pov_members.append([default])

            pov_dimensions.append(dim_name)

        # Build grid definition
        grid_definition = {
            "suppressMissingBlocks": True,
            "pov": {
                "members": pov_members
            },
            "columns": [
                {
                    "dimensions": [column_dimension],
                    "members": [[m] for m in column_members]
                }
            ],
            "rows": [
                {
                    "dimensions": [row_dimension],
                    "members": [[m] for m in row_members]
                }
            ]
        }

        return {
            "status": "success",
            "data": {
                "grid_definition": grid_definition,
                "metadata": {
                    "row_dimension": row_dimension,
                    "column_dimension": column_dimension,
                    "pov_dimensions": pov_dimensions,
                    "pov_defaults_used": [
                        dim for dim in pov_dimensions
                        if dim not in pov_selections
                    ]
                }
            }
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def profile_data(
    plan_type: str,
    sample_size: int = 5
) -> Dict[str, Any]:
    """Profile data across dimensions to find where values exist.

    This tool samples data at various dimension intersections to help
    identify where actual data is stored in the application.

    Args:
        plan_type: The plan type to profile (e.g., 'Plan1').
        sample_size: Number of sample queries per dimension.

    Returns:
        dict: Data profile showing which intersections have values.
    """
    global _discovered_structure

    validation_error = _validate_client()
    if validation_error:
        return validation_error

    try:
        # Get structure if not cached
        if not _discovered_structure:
            await discover_app_structure()

        dims = _discovered_structure.get("dimensions", [])
        if len(dims) < 2:
            return {
                "status": "error",
                "error": "Need at least 2 dimensions to profile"
            }

        profile_results = {
            "tested_intersections": [],
            "intersections_with_data": [],
            "empty_intersections": [],
            "errors": []
        }

        # Find suitable row and column dimensions
        row_dim = None
        col_dim = None

        for d in dims:
            if d["dim_type"].lower() == "account" and not row_dim:
                row_dim = d
            elif d["dim_type"].lower() in ["period", "time"] and not col_dim:
                col_dim = d

        # Fallback to first two dimensions
        if not row_dim:
            row_dim = dims[0]
        if not col_dim:
            col_dim = dims[1] if len(dims) > 1 else dims[0]

        # Build POV defaults
        pov_selections = {}
        for d in dims:
            if d["name"] not in [row_dim["name"], col_dim["name"]]:
                samples = d.get("sample_members", d.get("root_members", [""]))
                pov_selections[d["name"]] = samples[0] if samples else ""

        # Sample row members
        row_samples = row_dim.get("sample_members", row_dim.get("root_members", []))[:sample_size]
        col_samples = col_dim.get("sample_members", col_dim.get("root_members", []))[:sample_size]

        # Test intersections
        for row_member in row_samples:
            for col_member in col_samples:
                intersection = f"{row_dim['name']}:{row_member} x {col_dim['name']}:{col_member}"
                profile_results["tested_intersections"].append(intersection)

                try:
                    grid_result = await build_dynamic_grid(
                        row_dimension=row_dim["name"],
                        row_members=[row_member],
                        column_dimension=col_dim["name"],
                        column_members=[col_member],
                        pov_selections=pov_selections
                    )

                    if grid_result["status"] == "success":
                        grid_def = grid_result["data"]["grid_definition"]

                        # Execute the query
                        data_result = await _client.export_data_slice(
                            _app_name, plan_type, grid_def
                        )

                        # Check if we got data
                        has_data = False
                        if data_result and "rows" in data_result:
                            for row in data_result["rows"]:
                                if "data" in row and row["data"]:
                                    for val in row["data"]:
                                        if val is not None and val != "" and val != 0:
                                            has_data = True
                                            break

                        if has_data:
                            profile_results["intersections_with_data"].append({
                                "intersection": intersection,
                                "row_member": row_member,
                                "col_member": col_member,
                                "sample_value": data_result["rows"][0]["data"][0] if data_result.get("rows") else None
                            })
                        else:
                            profile_results["empty_intersections"].append(intersection)

                except Exception as e:
                    profile_results["errors"].append({
                        "intersection": intersection,
                        "error": str(e)
                    })

        return {
            "status": "success",
            "data": {
                "plan_type": plan_type,
                "row_dimension": row_dim["name"],
                "column_dimension": col_dim["name"],
                "pov_used": pov_selections,
                "profile": profile_results,
                "summary": {
                    "total_tested": len(profile_results["tested_intersections"]),
                    "with_data": len(profile_results["intersections_with_data"]),
                    "empty": len(profile_results["empty_intersections"]),
                    "errors": len(profile_results["errors"])
                }
            }
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def smart_retrieve_dynamic(
    plan_type: str,
    row_dimension: str,
    row_member: str,
    column_dimension: str,
    column_member: str,
    **pov_overrides
) -> Dict[str, Any]:
    """Smart data retrieval for any custom app with dynamic dimension handling.

    Unlike the hardcoded smart_retrieve, this works with any dimension structure.

    Args:
        plan_type: The plan type to query.
        row_dimension: Dimension for rows.
        row_member: Member for row dimension.
        column_dimension: Dimension for columns.
        column_member: Member for column dimension.
        **pov_overrides: Override specific POV dimensions (dim_name=member_name).

    Returns:
        dict: Retrieved data value with full context.
    """
    global _discovered_structure

    validation_error = _validate_client()
    if validation_error:
        return validation_error

    try:
        # Get structure if not cached
        if not _discovered_structure:
            await discover_app_structure()

        # Build POV selections from defaults + overrides
        pov_selections = {}
        for d in _discovered_structure.get("dimensions", []):
            dim_name = d["name"]
            if dim_name in [row_dimension, column_dimension]:
                continue

            if dim_name in pov_overrides:
                pov_selections[dim_name] = pov_overrides[dim_name]
            else:
                # Use first available member as default
                samples = d.get("sample_members", d.get("root_members", []))
                pov_selections[dim_name] = samples[0] if samples else ""

        # Build and execute grid
        grid_result = await build_dynamic_grid(
            row_dimension=row_dimension,
            row_members=[row_member],
            column_dimension=column_dimension,
            column_members=[column_member],
            pov_selections=pov_selections
        )

        if grid_result["status"] != "success":
            return grid_result

        grid_def = grid_result["data"]["grid_definition"]

        # Execute query
        data_result = await _client.export_data_slice(_app_name, plan_type, grid_def)

        # Extract value
        value = None
        if data_result and "rows" in data_result and len(data_result["rows"]) > 0:
            row = data_result["rows"][0]
            if "data" in row and len(row["data"]) > 0:
                try:
                    value = float(row["data"][0])
                except (ValueError, TypeError):
                    value = row["data"][0]

        return {
            "status": "success",
            "value": value,
            "data": data_result,
            "query_context": {
                "plan_type": plan_type,
                "row": {row_dimension: row_member},
                "column": {column_dimension: column_member},
                "pov": pov_selections
            }
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def export_app_metadata() -> Dict[str, Any]:
    """Export complete application metadata for offline analysis.

    Returns:
        dict: Full metadata export including all dimensions and members.
    """
    global _discovered_structure

    validation_error = _validate_client()
    if validation_error:
        return validation_error

    try:
        # Get full structure
        if not _discovered_structure:
            await discover_app_structure()

        full_export = {
            "app_name": _app_name,
            "structure": _discovered_structure,
            "dimensions_detail": {}
        }

        # Export each dimension's members
        for dim_info in _discovered_structure.get("dimensions", []):
            dim_name = dim_info["name"]
            try:
                members_response = await _client.get_members(_app_name, dim_name)
                full_export["dimensions_detail"][dim_name] = {
                    "type": dim_info["dim_type"],
                    "members": members_response.get("items", [])
                }
            except Exception as e:
                full_export["dimensions_detail"][dim_name] = {
                    "type": dim_info["dim_type"],
                    "error": str(e)
                }

        return {
            "status": "success",
            "data": full_export
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


# Tool definitions for MCP registration
TOOL_DEFINITIONS = [
    {
        "name": "discover_app_structure",
        "description": "Discover the complete structure of a Planning application - dimensions, types, plan types. Start here for unknown/custom apps.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "explore_dimension",
        "description": "Explore a dimension's hierarchy to understand its structure and find members",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dimension_name": {
                    "type": "string",
                    "description": "The name of the dimension to explore",
                },
                "parent_member": {
                    "type": "string",
                    "description": "Starting member (optional - None starts from root)",
                },
                "depth": {
                    "type": "integer",
                    "description": "How deep to explore (default: 2)",
                },
                "include_aliases": {
                    "type": "boolean",
                    "description": "Include member aliases (default: true)",
                },
            },
            "required": ["dimension_name"],
        },
    },
    {
        "name": "find_members",
        "description": "Search for members across dimensions by name or alias pattern",
        "inputSchema": {
            "type": "object",
            "properties": {
                "search_term": {
                    "type": "string",
                    "description": "Text to search for (case-insensitive, partial match)",
                },
                "dimension_name": {
                    "type": "string",
                    "description": "Specific dimension to search (optional - None searches all)",
                },
                "search_aliases": {
                    "type": "boolean",
                    "description": "Also search in aliases/descriptions (default: true)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results to return (default: 50)",
                },
            },
            "required": ["search_term"],
        },
    },
    {
        "name": "build_dynamic_grid",
        "description": "Build a grid definition dynamically for any custom app structure",
        "inputSchema": {
            "type": "object",
            "properties": {
                "row_dimension": {
                    "type": "string",
                    "description": "Dimension to place on rows",
                },
                "row_members": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Members for the row dimension",
                },
                "column_dimension": {
                    "type": "string",
                    "description": "Dimension to place on columns",
                },
                "column_members": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Members for the column dimension",
                },
                "pov_selections": {
                    "type": "object",
                    "description": "Dict of {dimension_name: member_name} for POV",
                },
            },
            "required": ["row_dimension", "row_members", "column_dimension", "column_members", "pov_selections"],
        },
    },
    {
        "name": "profile_data",
        "description": "Profile data across dimensions to find where values exist in the application",
        "inputSchema": {
            "type": "object",
            "properties": {
                "plan_type": {
                    "type": "string",
                    "description": "The plan type to profile",
                },
                "sample_size": {
                    "type": "integer",
                    "description": "Number of sample queries per dimension (default: 5)",
                },
            },
            "required": ["plan_type"],
        },
    },
    {
        "name": "smart_retrieve_dynamic",
        "description": "Smart data retrieval for any custom app - works with any dimension structure",
        "inputSchema": {
            "type": "object",
            "properties": {
                "plan_type": {
                    "type": "string",
                    "description": "The plan type to query",
                },
                "row_dimension": {
                    "type": "string",
                    "description": "Dimension for rows",
                },
                "row_member": {
                    "type": "string",
                    "description": "Member for row dimension",
                },
                "column_dimension": {
                    "type": "string",
                    "description": "Dimension for columns",
                },
                "column_member": {
                    "type": "string",
                    "description": "Member for column dimension",
                },
            },
            "required": ["plan_type", "row_dimension", "row_member", "column_dimension", "column_member"],
        },
    },
    {
        "name": "export_app_metadata",
        "description": "Export complete application metadata for offline analysis",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]
