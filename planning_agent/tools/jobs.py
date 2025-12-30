"""Job tools - list_jobs, get_job_status, execute_job."""

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


async def list_jobs() -> dict[str, Any]:
    """List recent jobs in the Planning application / Listar jobs recentes na aplicacao Planning.

    Returns:
        dict: List of recent jobs with status information.
    """
    jobs = await _client.list_jobs(_app_name)
    return {"status": "success", "data": jobs}


async def get_job_status(job_id: str) -> dict[str, Any]:
    """Get the status of a specific job / Obter o status de um job especifico.

    Args:
        job_id: The ID of the job to check.

    Returns:
        dict: Job status details.
    """
    status = await _client.get_job_status(_app_name, job_id)
    return {"status": "success", "data": status}


async def execute_job(
    job_type: str,
    job_name: str,
    parameters: Optional[dict[str, Any]] = None
) -> dict[str, Any]:
    """Execute a job (business rule, export metadata, cube refresh, etc.) / Executar um job.

    Args:
        job_type: Type of job to execute (e.g., 'Rules', 'Export Metadata', 'Cube Refresh').
        job_name: Name of the job to execute (must match a job definition).
        parameters: Optional parameters for the job.

    Returns:
        dict: Job submission result.
    """
    result = await _client.execute_job(_app_name, job_type, job_name, parameters)
    return {"status": "success", "data": result}


TOOL_DEFINITIONS = [
    {
        "name": "list_jobs",
        "description": "List recent jobs in the Planning application / Listar jobs recentes na aplicacao Planning",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_job_status",
        "description": "Get the status of a specific job / Obter o status de um job especifico",
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "The ID of the job to check / O ID do job para verificar",
                },
            },
            "required": ["job_id"],
        },
    },
    {
        "name": "execute_job",
        "description": "Execute a job (business rule, export metadata, cube refresh, etc.) / Executar um job",
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_type": {
                    "type": "string",
                    "description": "Type of job to execute (e.g., 'Rules', 'Export Metadata', 'Cube Refresh')",
                },
                "job_name": {
                    "type": "string",
                    "description": "Name of the job to execute (must match a job definition)",
                },
                "parameters": {
                    "type": "object",
                    "description": "Optional parameters for the job",
                },
            },
            "required": ["job_type", "job_name"],
        },
    },
]


