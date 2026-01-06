"""ADK Agent - Main agent definition with all Planning tools."""

import sys
from typing import Any, Optional

from planning_agent.config import config, PlanningConfig
from planning_agent.client.planning_client import PlanningClient
from planning_agent.services.feedback_service import (
    init_feedback_service,
    before_tool_callback,
    after_tool_callback,
    get_feedback_service
)
from planning_agent.services.rl_service import (
    init_rl_service,
    get_rl_service
)
from planning_agent.intelligence.orchestrator import PlanningOrchestrator

# Import all tool modules
from planning_agent.tools import application, jobs, dimensions, data, variables, documents, snapshots, feedback, discovery

# Global state
_planning_client: Optional[PlanningClient] = None
_app_name: Optional[str] = None
_session_state: dict[str, dict[str, Any]] = {}  # Track session state for RL
_orchestrator: Optional[PlanningOrchestrator] = None

from planning_agent.intelligence.expertise import SYSTEM_PROMPT_ADDITION, MODULE_EXPERTISE

# Agent instruction
AGENT_INSTRUCTION = f"""You are an expert assistant for Oracle EPM Cloud Planning (EPBCS).

{SYSTEM_PROMPT_ADDITION}

You help users with:
- Querying financial data (Revenue, Expense, Net Income) from Planning cubes
- Running business rules and calculations
- Managing dimension members and hierarchies
- Managing substitution variables and library documents
- Analyzing variances (Actual vs Forecast, YoY)

Respond in the same language as the user (English or Portuguese).
Always provide clear explanations of what you're doing and the results.

Available tools:
- get_application_info, get_rest_api_version: App details
- list_jobs, get_job_status, execute_job: Monitor and run jobs/rules
- get_dimensions, get_members, get_member: Explore dimensions
- export_data_slice, smart_retrieve, smart_retrieve_revenue, smart_retrieve_monthly, smart_retrieve_variance: Query data
- copy_data, clear_data: Data management
- get_substitution_variables, set_substitution_variable: Sub vars
- get_documents, get_snapshots: Library management
- submit_feedback, rate_last_tool, get_rle_dashboard: Feedback and RL performance
- agentic_query: Full reasoning pipeline for complex natural language queries

Discovery tools for custom/freeform apps (start here if you don't know the app structure):
- discover_app_structure: Discover all dimensions, types, and plan types in any custom app
- explore_dimension: Navigate dimension hierarchies to understand structure
- find_members: Search for members by name or alias across dimensions
- build_dynamic_grid: Auto-construct grid definitions for any dimension structure
- profile_data: Sample data to find where values exist in the application
- smart_retrieve_dynamic: Query data from any custom app with dynamic dimension handling
- export_app_metadata: Export full metadata for offline analysis
"""


def get_client() -> PlanningClient:
    """Get the Planning client instance."""
    global _planning_client
    if _planning_client is None:
        _planning_client = PlanningClient(config)
    return _planning_client


def get_app_name() -> Optional[str]:
    """Get the current application name."""
    return _app_name


async def initialize_agent(cfg: Optional[PlanningConfig] = None) -> str:
    """Initialize the agent and connect to Planning."""
    global _planning_client, _app_name

    use_config = cfg or config

    # Initialize Planning client
    _planning_client = PlanningClient(use_config)

    # Set client reference in all tool modules
    application.set_client(_planning_client)
    jobs.set_client(_planning_client)
    dimensions.set_client(_planning_client)
    data.set_client(_planning_client)
    variables.set_client(_planning_client)
    documents.set_client(_planning_client)
    snapshots.set_client(_planning_client)
    discovery.set_client(_planning_client)
    # feedback tool doesn't need client, it uses services

    # Initialize feedback service
    feedback_service = None
    try:
        feedback_service = init_feedback_service(use_config.database_url)
    except Exception as e:
        print(f"Warning: Could not initialize feedback service: {e}", file=sys.stderr)

    # Initialize RL service
    if use_config.rl_enabled and feedback_service:
        try:
            init_rl_service(
                feedback_service,
                use_config.database_url,
                exploration_rate=use_config.rl_exploration_rate,
                learning_rate=use_config.rl_learning_rate,
                discount_factor=use_config.rl_discount_factor,
                min_samples=use_config.rl_min_samples
            )
        except Exception as e:
            print(f"Warning: Could not initialize RL service: {e}", file=sys.stderr)

    # Try to connect and get application name
    try:
        apps = await _planning_client.get_applications()
        if apps and apps.get("items") and len(apps["items"]) > 0:
            _app_name = apps["items"][0]["name"]
            
            # Set app name in tool modules that need it
            jobs.set_app_name(_app_name)
            dimensions.set_app_name(_app_name)
            data.set_app_name(_app_name)
            variables.set_app_name(_app_name)
            documents.set_app_name(_app_name)
            discovery.set_app_name(_app_name)

            return _app_name
        return "Connected (no apps found)"
    except Exception as e:
        return f"Connection warning: {e}"


async def close_agent():
    """Clean up agent resources."""
    global _planning_client
    if _planning_client:
        await _planning_client.close()
        _planning_client = None


AGENTIC_TOOL_DEFINITION = {
    "name": "agentic_query",
    "description": "Process a natural language Planning query through the agentic reasoning pipeline.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "User query in natural language."},
            "session_id": {"type": "string", "description": "Optional session id for context.", "default": "default"},
        },
        "required": ["query"],
    },
}


def get_orchestrator() -> PlanningOrchestrator:
    """Get or create the agentic orchestrator."""
    global _orchestrator
    if _orchestrator is None:
        orchestrator = PlanningOrchestrator(
            db_url=config.database_url,
            anthropic_api_key=config.anthropic_api_key
        )
        handlers = {
            name: handler
            for name, handler in TOOL_HANDLERS.items()
            if name != "agentic_query"
        }
        orchestrator.set_tool_handlers(handlers)
        rl_service = get_rl_service()
        if rl_service:
            orchestrator.set_rl_service(rl_service)
        _orchestrator = orchestrator
    return _orchestrator


async def agentic_query(query: str, session_id: str = "default") -> dict[str, Any]:
    """Run the full agentic reasoning pipeline."""
    orchestrator = get_orchestrator()
    response = await orchestrator.process(query, session_id=session_id)
    
    data_res = {
        "intent": {
            "name": response.intent.name if response.intent else "unknown",
            "confidence": response.intent.confidence if response.intent else 0.0,
        },
        "plan": {
            "name": response.plan.name if response.plan else "None",
            "description": response.plan.description if response.plan else "None",
            "steps": [
                {
                    "tool": step.tool_name,
                    "parameters": step.parameters,
                    "description": step.description,
                    "status": step.status.value
                }
                for step in response.plan.steps
            ] if response.plan else [],
        },
        "results": response.results,
        "synthesis": response.synthesis,
        "recommendations": response.recommendations,
        "error_explanation": response.error_explanation,
    }
    
    return {
        "status": "success" if response.success else "error",
        "data": data_res,
        "error": response.error_explanation if not response.success else None,
    }


# Tool registry
TOOL_HANDLERS = {
    "get_application_info": application.get_application_info,
    "get_rest_api_version": application.get_rest_api_version,
    "list_jobs": jobs.list_jobs,
    "get_job_status": jobs.get_job_status,
    "execute_job": jobs.execute_job,
    "get_dimensions": dimensions.get_dimensions,
    "get_members": dimensions.get_members,
    "get_member": dimensions.get_member,
    "export_data_slice": data.export_data_slice,
    "smart_retrieve": data.smart_retrieve,
    "smart_retrieve_revenue": data.smart_retrieve_revenue,
    "smart_retrieve_monthly": data.smart_retrieve_monthly,
    "smart_retrieve_variance": data.smart_retrieve_variance,
    "copy_data": data.copy_data,
    "clear_data": data.clear_data,
    "get_substitution_variables": variables.get_substitution_variables,
    "set_substitution_variable": variables.set_substitution_variable,
    "get_documents": documents.get_documents,
    "get_snapshots": snapshots.get_snapshots,
    "submit_feedback": feedback.submit_feedback,
    "get_recent_executions": feedback.get_recent_executions,
    "rate_last_tool": feedback.rate_last_tool,
    "get_rle_dashboard": feedback.get_rle_dashboard,
    "agentic_query": agentic_query,
    # Discovery tools for custom/freeform apps
    "discover_app_structure": discovery.discover_app_structure,
    "explore_dimension": discovery.explore_dimension,
    "find_members": discovery.find_members,
    "build_dynamic_grid": discovery.build_dynamic_grid,
    "profile_data": discovery.profile_data,
    "smart_retrieve_dynamic": discovery.smart_retrieve_dynamic,
    "export_app_metadata": discovery.export_app_metadata,
}

ALL_TOOL_DEFINITIONS = (
    application.TOOL_DEFINITIONS +
    jobs.TOOL_DEFINITIONS +
    dimensions.TOOL_DEFINITIONS +
    data.TOOL_DEFINITIONS +
    variables.TOOL_DEFINITIONS +
    documents.TOOL_DEFINITIONS +
    snapshots.TOOL_DEFINITIONS +
    feedback.TOOL_DEFINITIONS +
    discovery.TOOL_DEFINITIONS +
    [AGENTIC_TOOL_DEFINITION]
)


async def execute_tool(
    tool_name: str,
    arguments: dict[str, Any],
    session_id: str = "default",
    user_query: str = "",
    use_rl: bool = True
) -> dict[str, Any]:
    """Execute a tool by name."""
    handler = TOOL_HANDLERS.get(tool_name)
    if not handler:
        return {"status": "error", "error": f"Unknown tool: {tool_name}"}

    if session_id not in _session_state:
        _session_state[session_id] = {
            "tool_sequence": [],
            "previous_tool": None,
            "session_length": 0,
            "user_query": user_query
        }

    session_state = _session_state[session_id]
    
    try:
        before_tool_callback(session_id, tool_name, arguments)
    except: pass

    try:
        result = await handler(**arguments)
        session_state["tool_sequence"].append(tool_name)
        session_state["previous_tool"] = tool_name
        session_state["session_length"] += 1

        try:
            execution_id = after_tool_callback(session_id, tool_name, arguments, result)
            if execution_id and execution_id > 0:
                result["execution_id"] = execution_id
                # Add feedback hint for RL rating
                result["_feedback_hint"] = (
                    f"Was this helpful? Rate with: rate_last_tool('good') or rate_last_tool('bad') "
                    f"or submit_feedback(execution_id={execution_id}, rating=1-5)"
                )

            rl_service = get_rl_service()
            if rl_service and use_rl:
                # Simple policy update could go here
                pass
        except: pass

        return result
    except Exception as e:
        error_result = {"status": "error", "error": str(e)}
        try: after_tool_callback(session_id, tool_name, arguments, error_result)
        except: pass
        return error_result


def finalize_session(session_id: str, outcome: str = "success"):
    if session_id not in _session_state: return
    session_state = _session_state[session_id]
    tool_sequence = session_state.get("tool_sequence", [])
    if not tool_sequence: return
    rl_service = get_rl_service()
    if rl_service:
        try:
            reward = 10.0 if outcome == "success" else (5.0 if outcome == "partial" else -5.0)
            rl_service.log_episode(session_id, tool_sequence, reward, outcome)
        except: pass


def get_tool_definitions() -> list[dict]:
    return ALL_TOOL_DEFINITIONS
