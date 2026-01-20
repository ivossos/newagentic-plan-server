"""Exploration tools - Semantic search and intelligent member resolution."""

from typing import Any, Optional

from planning_agent.services.semantic_search import (
    get_semantic_search_service,
    SemanticSearchService
)


async def search_members(
    query: str,
    dimension: Optional[str] = None,
    top_k: int = 10,
    threshold: float = 0.3
) -> dict[str, Any]:
    """Search for dimension members using natural language.

    Combines fuzzy matching with semantic search to find members that match
    user intent. Supports Planning-specific synonyms (revenue, expense, etc.).

    Examples:
    - "revenue" -> finds Account members like 400000, Total Revenue
    - "chicago hotel" -> finds Entity members like E501
    - "rooms" -> finds 410000-Rooms Revenue
    - "cash" -> finds 111000-Cash and Cash Equivalent

    Args:
        query: Natural language search query
        dimension: Optional dimension to filter by (Account, Entity, etc.)
        top_k: Maximum number of results (default: 10)
        threshold: Minimum similarity score 0-1 (default: 0.3)

    Returns:
        dict: Matching members with similarity scores.
    """
    service = get_semantic_search_service()
    if not service:
        return {
            "status": "error",
            "error": "Semantic search service not initialized. Run index_from_csvs first."
        }

    try:
        results = service.search(
            query=query,
            dimension=dimension,
            top_k=top_k,
            threshold=threshold
        )

        return {
            "status": "success",
            "data": {
                "query": query,
                "dimension_filter": dimension,
                "count": len(results),
                "results": results
            }
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def resolve_member(
    fuzzy_input: str,
    dimension: Optional[str] = None,
    confidence_threshold: float = 0.5
) -> dict[str, Any]:
    """Resolve a fuzzy/approximate member input to an exact member name.

    Useful for handling user input that may not exactly match member names.
    First tries exact matching, then falls back to semantic search.

    Examples:
    - "rev" -> "400000" (Total Revenue)
    - "chicago" -> "E501" (L7 Chicago)
    - "actual" -> "Actual" (Scenario)

    Args:
        fuzzy_input: User's approximate member name
        dimension: Optional dimension to constrain search
        confidence_threshold: Minimum score to accept match (default: 0.5)

    Returns:
        dict: Best matching member or error if no confident match.
    """
    service = get_semantic_search_service()
    if not service:
        return {
            "status": "error",
            "error": "Semantic search service not initialized"
        }

    try:
        result = service.resolve_member(
            fuzzy_input=fuzzy_input,
            dimension=dimension,
            confidence_threshold=confidence_threshold
        )

        if result:
            return {
                "status": "success",
                "data": {
                    "input": fuzzy_input,
                    "resolved": result
                }
            }
        else:
            return {
                "status": "not_found",
                "message": f"No confident match found for '{fuzzy_input}'",
                "data": {
                    "input": fuzzy_input,
                    "dimension": dimension,
                    "threshold": confidence_threshold
                }
            }
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def get_semantic_index_stats() -> dict[str, Any]:
    """Get statistics about the semantic search index.

    Shows indexed dimensions, member counts, and embedding model information.

    Returns:
        dict: Index statistics including dimensions and counts.
    """
    service = get_semantic_search_service()
    if not service:
        return {
            "status": "error",
            "error": "Semantic search service not initialized"
        }

    try:
        stats = service.get_index_stats()
        indexed_dims = service.get_indexed_dimensions()

        return {
            "status": "success",
            "data": {
                "indexed_dimensions": indexed_dims,
                "statistics": stats
            }
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def reindex_dimension(
    dimension: str,
    data_dir: Optional[str] = None
) -> dict[str, Any]:
    """Re-index a specific dimension from CSV data.

    Useful when dimension metadata has been updated and needs to be
    re-indexed for semantic search.

    Args:
        dimension: Dimension name to re-index (Account, Entity, etc.)
        data_dir: Optional directory containing CSV files

    Returns:
        dict: Status and count of indexed members.
    """
    service = get_semantic_search_service()
    if not service:
        return {
            "status": "error",
            "error": "Semantic search service not initialized"
        }

    try:
        from planning_agent.services.semantic_search import index_from_csvs
        from pathlib import Path

        if data_dir is None:
            data_dir = Path(__file__).parent.parent.parent / "data"
        else:
            data_dir = Path(data_dir)

        # Map dimension to filename
        filename = f"ExportedMetadata_{dimension}.csv"
        filepath = data_dir / filename

        if not filepath.exists():
            return {
                "status": "error",
                "error": f"CSV file not found: {filepath}"
            }

        # Index just this dimension
        import csv

        members = []
        with open(filepath, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            next(reader, None)  # Skip header

            for row in reader:
                if not row or not row[0]:
                    continue

                member_name = row[0].strip()
                parent = row[1].strip() if len(row) > 1 and row[1] else None
                alias = row[2].strip() if len(row) > 2 and row[2] and row[2] != member_name else None

                members.append({
                    "name": member_name,
                    "parent": parent,
                    "alias": alias
                })

        if members:
            count = service.index_members_batch(dimension, members)
            return {
                "status": "success",
                "message": f"Re-indexed {count} members for {dimension}",
                "data": {
                    "dimension": dimension,
                    "member_count": count
                }
            }
        else:
            return {
                "status": "warning",
                "message": f"No members found in {filepath}"
            }

    except Exception as e:
        return {"status": "error", "error": str(e)}


TOOL_DEFINITIONS = [
    {
        "name": "search_members",
        "description": "Search for dimension members using natural language with semantic matching / Buscar membros usando linguagem natural",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language search query (e.g., 'revenue', 'chicago hotel', 'cash')",
                },
                "dimension": {
                    "type": "string",
                    "description": "Optional dimension to filter by (Account, Entity, Scenario, etc.)",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Maximum number of results (default: 10)",
                },
                "threshold": {
                    "type": "number",
                    "description": "Minimum similarity score 0-1 (default: 0.3)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "resolve_member",
        "description": "Resolve fuzzy/approximate member input to exact member name / Resolver entrada aproximada para nome exato de membro",
        "inputSchema": {
            "type": "object",
            "properties": {
                "fuzzy_input": {
                    "type": "string",
                    "description": "User's approximate member name",
                },
                "dimension": {
                    "type": "string",
                    "description": "Optional dimension to constrain search",
                },
                "confidence_threshold": {
                    "type": "number",
                    "description": "Minimum score to accept match (default: 0.5)",
                },
            },
            "required": ["fuzzy_input"],
        },
    },
    {
        "name": "get_semantic_index_stats",
        "description": "Get statistics about the semantic search index / Obter estatisticas do indice semantico",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "reindex_dimension",
        "description": "Re-index a specific dimension from CSV data / Reindexar uma dimensao especifica",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dimension": {
                    "type": "string",
                    "description": "Dimension name to re-index (Account, Entity, etc.)",
                },
                "data_dir": {
                    "type": "string",
                    "description": "Optional directory containing CSV files",
                },
            },
            "required": ["dimension"],
        },
    },
]
