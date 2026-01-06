"""Web Server - FastAPI REST API for ChatGPT and other clients."""

import json
import os
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

from planning_agent.config import config
from planning_agent.agent import (
    initialize_agent,
    close_agent,
    execute_tool,
    get_tool_definitions,
)
from planning_agent.services.feedback_service import get_feedback_service
from planning_agent.services.rl_service import get_rl_service


class ToolCallRequest(BaseModel):
    """Request to call a tool."""
    tool_name: str
    arguments: dict[str, Any] = {}
    session_id: str = "default"


class ToolCallResponse(BaseModel):
    """Response from a tool call."""
    status: str
    data: Optional[Any] = None
    error: Optional[str] = None


class FeedbackRequest(BaseModel):
    """Request to submit feedback for a tool execution."""
    execution_id: int
    rating: int  # 1-5
    feedback: Optional[str] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    await initialize_agent()
    yield
    await close_agent()


app = FastAPI(
    title="Planning Agent API",
    description="Oracle Planning Agentic MCP Server API for ChatGPT",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for web UI
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "name": "Planning Agent API",
        "version": "0.1.0",
        "status": "healthy",
        "mock_mode": config.planning_mock_mode
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/.well-known/mcp.json")
async def mcp_discovery():
    """MCP server discovery endpoint."""
    return {
        "info": {
            "title": "Oracle EPM Planning Agent",
            "version": "0.1.0",
            "description": "Oracle EPM Planning Agent with MCP support for querying financial data"
        },
        "servers": [
            "https://fastmcp-plan-agent-241840460713.us-central1.run.app/mcp"
        ]
    }


@app.get("/api-schema.json")
async def openapi_spec():
    """OpenAPI spec for ChatGPT Actions."""
    tools = get_tool_definitions()
    paths = {}

    response_schema = {
        "type": "object",
        "properties": {
            "status": {"type": "string", "description": "Status of the operation"},
            "data": {"type": "object", "description": "Result data from the tool"},
            "error": {"type": "string", "description": "Error message if any"}
        }
    }

    for tool in tools:
        tool_name = tool["name"]
        input_schema = tool.get("inputSchema", {"type": "object", "properties": {}})
        if "properties" not in input_schema:
            input_schema["properties"] = {}

        paths[f"/execute"] = paths.get(f"/execute", {})
        paths[f"/tools/{tool_name}"] = {
            "post": {
                "operationId": tool_name,
                "summary": tool.get("description", "")[:100],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": input_schema
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Successful response",
                        "content": {
                            "application/json": {
                                "schema": response_schema
                            }
                        }
                    }
                }
            }
        }

    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Oracle EPM Planning Agent",
            "version": "0.1.0",
            "description": "Oracle EPM Planning Agent API for querying financial data from EPBCS"
        },
        "servers": [
            {"url": "https://fastmcp-plan-agent-241840460713.us-central1.run.app"}
        ],
        "paths": paths
    }


@app.get("/tools")
async def list_tools():
    """List available Planning tools."""
    return {"tools": get_tool_definitions()}


@app.post("/tools/{tool_name}", response_model=ToolCallResponse)
async def call_tool(tool_name: str, request: Request):
    """Call a specific tool. The request body is used directly as arguments."""
    try:
        # Parse request body as arguments directly
        body = await request.body()
        if body:
            arguments = json.loads(body)
        else:
            arguments = {}

        # tool_name comes from URL path, arguments from body
        result = await execute_tool(
            tool_name,
            arguments,
            "default"
        )
        return ToolCallResponse(
            status=result.get("status", "success"),
            data=result.get("data"),
            error=result.get("error")
        )
    except json.JSONDecodeError:
        # Empty or invalid JSON - call with no arguments
        result = await execute_tool(tool_name, {}, "default")
        return ToolCallResponse(
            status=result.get("status", "success"),
            data=result.get("data"),
            error=result.get("error")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/execute", response_model=ToolCallResponse)
async def execute(request: ToolCallRequest):
    """Execute a tool by name."""
    try:
        result = await execute_tool(
            request.tool_name,
            request.arguments,
            request.session_id
        )
        return ToolCallResponse(
            status=result.get("status", "success"),
            data=result.get("data"),
            error=result.get("error")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


import asyncio

async def sse_stream():
    """Generate SSE stream with tools info."""
    tools = get_tool_definitions()
    # Send endpoint event first (MCP protocol)
    yield f"event: endpoint\ndata: /mcp\n\n"
    # Send tools list
    yield f"event: tools\ndata: {json.dumps({'tools': tools})}\n\n"
    # Keep connection alive with periodic pings
    while True:
        await asyncio.sleep(30)
        yield f": ping\n\n"


@app.get("/mcp")
async def mcp_get(request: Request):
    """GET endpoint for MCP - returns SSE stream (for ChatGPT)."""
    accept = request.headers.get("accept", "")
    if "text/event-stream" in accept:
        return StreamingResponse(
            sse_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    # Fallback to JSON for non-SSE clients
    return {"tools": get_tool_definitions()}


@app.post("/mcp")
async def mcp_message(request: Request):
    """Handle MCP-style JSON-RPC messages (for ChatGPT Custom GPT)."""
    try:
        body = await request.body()
        if not body:
            # Empty body - return tools list
            return {"tools": get_tool_definitions()}

        data = json.loads(body)
    except json.JSONDecodeError:
        # Invalid JSON - return tools list
        return {"tools": get_tool_definitions()}

    method = data.get("method", "")
    params = data.get("params", {})

    if method == "tools/list" or not method:
        return {"tools": get_tool_definitions()}

    elif method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        result = await execute_tool(tool_name, arguments)
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result, indent=2, ensure_ascii=False)
                }
            ]
        }

    # Handle direct tool call format (name + arguments at top level)
    elif "name" in data:
        tool_name = data.get("name")
        arguments = data.get("arguments", {})
        result = await execute_tool(tool_name, arguments)
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result, indent=2, ensure_ascii=False)
                }
            ]
        }

    else:
        # Unknown format - return tools list
        return {"tools": get_tool_definitions()}


# =============================================================================
# Feedback API Endpoints for RL Rating System
# =============================================================================

@app.post("/api/feedback")
async def submit_feedback_api(request: FeedbackRequest):
    """Submit user feedback/rating for a tool execution."""
    if request.rating < 1 or request.rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")

    feedback_service = get_feedback_service()
    if not feedback_service:
        raise HTTPException(status_code=503, detail="Feedback service not available")

    try:
        feedback_service.add_user_feedback(
            execution_id=request.execution_id,
            rating=request.rating,
            feedback=request.feedback
        )

        # Update RL policy retroactively
        rl_service = get_rl_service()
        rl_updated = False
        if rl_service:
            try:
                rl_updated = rl_service.update_policy_with_feedback(request.execution_id, request.rating)
            except Exception:
                pass

        return {
            "status": "success",
            "message": f"Feedback submitted: {request.rating} stars",
            "execution_id": request.execution_id,
            "rl_updated": rl_updated
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/executions")
async def get_executions_api(tool_name: Optional[str] = None, limit: int = 20):
    """Get recent tool executions for rating."""
    feedback_service = get_feedback_service()
    if not feedback_service:
        raise HTTPException(status_code=503, detail="Feedback service not available")

    try:
        executions = feedback_service.get_recent_executions(tool_name=tool_name, limit=limit)
        return {
            "status": "success",
            "data": [
                {
                    "id": e.id,
                    "tool_name": e.tool_name,
                    "success": e.success,
                    "execution_time_ms": e.execution_time_ms,
                    "user_rating": e.user_rating,
                    "user_feedback": e.user_feedback,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                    "arguments": e.arguments[:100] + "..." if e.arguments and len(e.arguments) > 100 else e.arguments
                }
                for e in executions
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/metrics")
async def get_metrics_api():
    """Get tool performance metrics for the dashboard."""
    feedback_service = get_feedback_service()
    rl_service = get_rl_service()

    if not feedback_service:
        raise HTTPException(status_code=503, detail="Feedback service not available")

    try:
        tool_metrics = feedback_service.get_tool_metrics()
        successful_sequences = []
        if rl_service:
            successful_sequences = rl_service.get_successful_sequences(limit=5)

        total_calls = sum(m.get("total_calls", 0) for m in tool_metrics)
        avg_success = sum(m.get("success_rate", 0) for m in tool_metrics) / len(tool_metrics) if tool_metrics else 0

        return {
            "status": "success",
            "data": {
                "summary": {
                    "total_executions": total_calls,
                    "avg_success_rate": round(avg_success, 2),
                    "active_tools": len(tool_metrics),
                    "rl_enabled": rl_service is not None
                },
                "tool_performance": sorted(tool_metrics, key=lambda x: x.get("total_calls", 0), reverse=True),
                "recent_successful_paths": successful_sequences
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def main():
    """Entry point for web server."""
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )


if __name__ == "__main__":
    main()
