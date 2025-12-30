"""Feedback tools for rating tool executions and improving RL learning."""

from typing import Any, Optional

from planning_agent.services.feedback_service import get_feedback_service
from planning_agent.services.rl_service import get_rl_service


async def submit_feedback(
    execution_id: int,
    rating: int,
    feedback: Optional[str] = None
) -> dict[str, Any]:
    """Submit user feedback for a tool execution to improve RL learning.
    
    This tool allows you to rate a tool execution (1-5 stars) and provide
    optional feedback. This helps the RL system learn which tools work best
    for your use cases and improves future recommendations.
    
    Args:
        execution_id: The ID of the tool execution to rate (from tool result)
        rating: Rating from 1-5 stars (5 = excellent, 1 = poor)
        feedback: Optional text feedback about the execution
    
    Returns:
        dict: Status of feedback submission
    """
    if rating < 1 or rating > 5:
        return {
            "status": "error",
            "error": f"Rating must be between 1 and 5, got {rating}"
        }
    
    feedback_service = get_feedback_service()
    if not feedback_service:
        return {
            "status": "error",
            "error": "Feedback service not available"
        }
    
    try:
        feedback_service.add_user_feedback(
            execution_id=execution_id,
            rating=rating,
            feedback=feedback
        )
        
        # Update RL policy retroactively with the new rating
        rl_updated = False
        rl_service = get_rl_service()
        if rl_service:
            try:
                rl_updated = rl_service.update_policy_with_feedback(execution_id, rating)
            except Exception:
                pass  # RL update is optional
        
        return {
            "status": "success",
            "message": f"Feedback submitted: {rating} stars",
            "execution_id": execution_id,
            "rating": rating,
            "feedback": feedback,
            "rl_updated": rl_updated
        }
    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to submit feedback: {str(e)}"
        }


async def get_recent_executions(
    tool_name: Optional[str] = None,
    limit: int = 10
) -> dict[str, Any]:
    """Get recent tool executions that can be rated.
    
    This tool helps you find tool executions that haven't been rated yet,
    so you can provide feedback to improve RL learning.
    
    Args:
        tool_name: Optional filter by specific tool name
        limit: Maximum number of executions to return (default: 10)
    
    Returns:
        dict: List of recent executions with their details
    """
    feedback_service = get_feedback_service()
    if not feedback_service:
        return {
            "status": "error",
            "error": "Feedback service not available"
        }
    
    try:
        executions = feedback_service.get_recent_executions(
            tool_name=tool_name,
            limit=limit
        )
        
        # Format executions for display
        formatted_executions = []
        for exec in executions:
            formatted_executions.append({
                "execution_id": exec.id,
                "tool_name": exec.tool_name,
                "success": exec.success,
                "user_rating": exec.user_rating,
                "execution_time_ms": exec.execution_time_ms,
                "created_at": exec.created_at.isoformat() if exec.created_at else None,
                "user_feedback": exec.user_feedback
            })
        
        return {
            "status": "success",
            "data": {
                "executions": formatted_executions,
                "total": len(formatted_executions)
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to get recent executions: {str(e)}"
        }


# Global tracking of last execution per session
_last_executions: dict[str, dict] = {}


def track_last_execution(session_id: str, execution_id: int, tool_name: str, context_hash: str = None):
    """Track the last execution for a session (called from agent.py)."""
    _last_executions[session_id] = {
        "execution_id": execution_id,
        "tool_name": tool_name,
        "context_hash": context_hash
    }


def get_last_execution(session_id: str) -> dict:
    """Get the last execution for a session."""
    return _last_executions.get(session_id, {})


async def rate_last_tool(
    rating: str,
    session_id: str = "default"
) -> dict[str, Any]:
    """Rate the last tool execution with a simple good/bad rating.
    
    This is a quick way to provide feedback after a tool execution.
    Use this after asking the user if the result was helpful.
    
    Args:
        rating: "good" (5 stars), "bad" (1 star), or 1-5 number
        session_id: Session ID (default: "default")
    
    Returns:
        dict: Status of feedback submission
    """
    # Convert rating to numeric
    rating_map = {"good": 5, "bad": 1, "ok": 3, "great": 5, "poor": 2}
    
    if isinstance(rating, str):
        rating_lower = rating.lower().strip()
        if rating_lower in rating_map:
            numeric_rating = rating_map[rating_lower]
        elif rating_lower.isdigit():
            numeric_rating = int(rating_lower)
        else:
            return {
                "status": "error",
                "error": f"Invalid rating: {rating}. Use good/bad or 1-5."
            }
    else:
        numeric_rating = int(rating)
    
    if numeric_rating < 1 or numeric_rating > 5:
        return {
            "status": "error",
            "error": f"Rating must be 1-5, got {numeric_rating}"
        }
    
    # Get last execution for this session
    last_exec = get_last_execution(session_id)
    if not last_exec:
        return {
            "status": "error",
            "error": "No recent tool execution found to rate"
        }
    
    execution_id = last_exec.get("execution_id")
    
    # Submit the feedback
    return await submit_feedback(
        execution_id=execution_id,
        rating=numeric_rating,
        feedback=f"Quick rating: {rating}"
    )


async def get_rle_dashboard() -> dict[str, Any]:
    """Get a comprehensive dashboard of RL performance and tool metrics.
    
    This tool provides an overview of the Reinforcement Learning engine's
    performance, including tool success rates, user ratings, and recent
    successful tool sequences.
    
    Returns:
        dict: RL performance dashboard data
    """
    feedback_service = get_feedback_service()
    rl_service = get_rl_service()
    
    if not feedback_service:
        return {
            "status": "error",
            "error": "Feedback service not available"
        }
    
    try:
        # 1. Get tool metrics
        tool_metrics = feedback_service.get_tool_metrics()
        
        # 2. Get successful sequences
        successful_sequences = []
        if rl_service:
            successful_sequences = rl_service.get_successful_sequences(limit=5)
        
        # 3. Calculate summary stats
        total_calls = sum(m.get("total_calls", 0) for m in tool_metrics)
        avg_success_rate = sum(m.get("success_rate", 0) for m in tool_metrics) / len(tool_metrics) if tool_metrics else 0
        
        return {
            "status": "success",
            "data": {
                "summary": {
                    "total_executions": total_calls,
                    "avg_success_rate": round(avg_success_rate, 2),
                    "active_tools": len(tool_metrics),
                    "rl_enabled": rl_service is not None
                },
                "tool_performance": sorted(tool_metrics, key=lambda x: x.get("success_rate", 0), reverse=True),
                "recent_successful_paths": successful_sequences
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to generate RLE dashboard: {str(e)}"
        }


TOOL_DEFINITIONS = [
    {
        "name": "submit_feedback",
        "description": "Submit user feedback (rating 1-5 stars) for a tool execution to improve RL learning / Enviar feedback do usuario para melhorar aprendizado RL",
        "inputSchema": {
            "type": "object",
            "properties": {
                "execution_id": {
                    "type": "integer",
                    "description": "The ID of the tool execution to rate (found in tool result or from get_recent_executions)"
                },
                "rating": {
                    "type": "integer",
                    "description": "Rating from 1-5 stars (5 = excellent, 4 = good, 3 = average, 2 = poor, 1 = bad)",
                    "minimum": 1,
                    "maximum": 5
                },
                "feedback": {
                    "type": "string",
                    "description": "Optional text feedback about the execution"
                }
            },
            "required": ["execution_id", "rating"]
        }
    },
    {
        "name": "get_recent_executions",
        "description": "Get recent tool executions that can be rated / Obter execucoes recentes que podem ser avaliadas",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tool_name": {
                    "type": "string",
                    "description": "Optional filter by specific tool name"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of executions to return (default: 10)",
                    "default": 10
                }
            }
        }
    },
    {
        "name": "rate_last_tool",
        "description": "Rate the last tool execution with good/bad. Call after asking if the result was helpful.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "rating": {
                    "type": "string",
                    "description": "Rating: 'good' (helpful), 'bad' (not helpful), or 1-5",
                    "enum": ["good", "bad", "ok", "great", "poor", "1", "2", "3", "4", "5"]
                },
                "session_id": {
                    "type": "string",
                    "description": "Session ID (optional, defaults to 'default')",
                    "default": "default"
                }
            },
            "required": ["rating"]
        }
    },
    {
        "name": "get_rle_dashboard",
        "description": "Get a comprehensive dashboard of RL performance and tool metrics / Obter dashboard de performance do RL",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]





