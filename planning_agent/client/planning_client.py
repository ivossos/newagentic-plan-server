"""Planning HTTP Client - Async client for Oracle Planning REST API."""

import base64
from typing import Any, Optional
from urllib.parse import quote

import httpx

from planning_agent.config import PlanningConfig
from planning_agent.client.mock_data import (
    MOCK_APPLICATIONS,
    MOCK_JOBS,
    MOCK_JOB_STATUS,
    MOCK_JOB_RESULT,
    MOCK_DIMENSIONS,
    MOCK_MEMBERS,
    MOCK_MEMBER,
    MOCK_DATA_SLICE,
    MOCK_SUBSTITUTION_VARIABLES,
    MOCK_DOCUMENTS,
    MOCK_SNAPSHOTS,
)
from planning_agent.utils.cache import (
    load_members_from_cache,
    save_members_to_cache,
)


class PlanningClient:
    """Async HTTP client for Oracle Planning REST API."""

    def __init__(self, config: PlanningConfig):
        self.config = config
        self.admin_mode = False
        self._client: Optional[httpx.AsyncClient] = None
        self._is_fccs_app: Optional[bool] = None  # Cache for FCCS detection

        if not config.planning_mock_mode:
            if not all([config.planning_url, config.planning_username, config.planning_password]):
                raise ValueError(
                    "Missing Planning credentials (URL, USERNAME, PASSWORD) required for real connection."
                )

            # Basic Auth header
            auth_string = f"{config.planning_username}:{config.planning_password}"
            auth_header = base64.b64encode(auth_string.encode()).decode()

            base_url = f"{config.planning_url}/HyperionPlanning/rest/{config.planning_api_version}/applications"

            headers = {
                "Authorization": f"Basic {auth_header}",
                "Content-Type": "application/json",
            }

            self._client = httpx.AsyncClient(
                base_url=base_url,
                headers=headers,
                timeout=60.0,
            )

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()

    def _get_query_params(self, has_existing_query: bool = False) -> str:
        """Get admin mode query parameter if needed."""
        if not self.admin_mode:
            return ""
        return "&adminMode=true" if has_existing_query else "?adminMode=true"

    # ========== Application Methods ==========

    async def get_applications(self) -> dict[str, Any]:
        """Get Planning applications / Obter aplicacoes Planning."""
        if self.config.planning_mock_mode:
            return MOCK_APPLICATIONS

        response = await self._client.get("/")
        response.raise_for_status()
        data = response.json()

        # Check if application is in admin mode
        # Also detect if it's an FCCS app
        if data.get("items") and len(data["items"]) > 0:
            if data["items"][0].get("adminMode"):
                self.admin_mode = True
            
            # Detect FCCS app by checking application type or name
            app_type = data["items"][0].get("type", "").lower()
            app_name = data["items"][0].get("name", "").lower()
            self._is_fccs_app = (
                "fccs" in app_type or 
                "consolidation" in app_type or
                "consol" in app_name
            )

        return data
    
    def _is_fccs_application(self, app_name: str) -> bool:
        """Check if an application is an FCCS app / Verificar se e uma aplicacao FCCS."""
        # Use cached value if available
        if self._is_fccs_app is not None:
            return self._is_fccs_app
        
        # Check by app name (common FCCS app names)
        app_name_lower = app_name.lower()
        fccs_indicators = ["consol", "fccs", "consolidation"]
        return any(indicator in app_name_lower for indicator in fccs_indicators)

    async def get_rest_api_version(self) -> dict[str, Any]:
        """Get REST API version / Obter versao da API REST."""
        if self.config.planning_mock_mode:
            return {"version": self.config.planning_api_version, "apiVersion": "3.0"}

        # Try version endpoints
        for endpoint in ["/rest/version", "/version", "/api/version"]:
            try:
                response = await self._client.get(endpoint)
                if response.status_code == 200:
                    return response.json()
            except Exception:
                continue

        return {
            "version": self.config.planning_api_version,
            "note": "Version endpoint not available, using configured version"
        }

    # ========== Job Methods ==========

    async def list_jobs(self, app_name: str) -> dict[str, Any]:
        """List jobs / Listar trabalhos."""
        if self.config.planning_mock_mode:
            return MOCK_JOBS

        try:
            response = await self._client.get(
                f"/{app_name}/jobs{self._get_query_params()}"
            )
            if response.status_code == 200:
                return response.json()
            return {"items": []}
        except Exception as e:
            return {"items": [], "error": str(e)}

    async def get_job_status(self, app_name: str, job_id: str) -> dict[str, Any]:
        """Get job status / Obter status do trabalho."""
        if self.config.planning_mock_mode:
            return MOCK_JOB_STATUS.get(
                job_id,
                {"jobId": job_id, "status": "Unknown", "details": "Mock job not found"}
            )

        response = await self._client.get(
            f"/{app_name}/jobs/{job_id}{self._get_query_params()}"
        )
        response.raise_for_status()
        return response.json()

    async def execute_job(
        self,
        app_name: str,
        job_type: str,
        job_name: str,
        parameters: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Execute a job (business rule, export metadata, etc.) / Executar um job."""
        if self.config.planning_mock_mode:
            return {**MOCK_JOB_RESULT, "jobName": job_name, "jobType": job_type}

        payload = {
            "jobType": job_type,
            "jobName": job_name,
            "parameters": parameters or {}
        }
        response = await self._client.post(
            f"/{app_name}/jobs{self._get_query_params()}",
            json=payload
        )
        response.raise_for_status()
        return response.json()

    # ========== Dimension Methods ==========

    async def get_dimensions(self, app_name: str) -> dict[str, Any]:
        """Get dimensions / Obter dimensoes."""
        if self.config.planning_mock_mode:
            return MOCK_DIMENSIONS

        # Try multiple endpoints
        endpoints = [
            f"/{app_name}/dimensions{self._get_query_params()}",
            f"/{app_name}/dimensions",
            f"/{app_name}/metadata/dimensions{self._get_query_params()}",
            f"/{app_name}/metadata/dimensions",
        ]

        for endpoint in endpoints:
            try:
                response = await self._client.get(endpoint)
                if response.status_code == 200:
                    return response.json()
            except Exception:
                continue

        # Fallback dimensions - check if it's an FCCS app
        if self._is_fccs_application(app_name):
            # FCCS standard dimensions
            return {
                "items": [
                    {"name": "Years", "type": "Time"},
                    {"name": "Period", "type": "Time"},
                    {"name": "Scenario", "type": "Scenario"},
                    {"name": "View", "type": "View"},
                    {"name": "Entity", "type": "Entity"},
                    {"name": "Consolidation", "type": "Consolidation"},
                    {"name": "Account", "type": "Account"},
                    {"name": "ICP", "type": "ICP"},
                    {"name": "Data Source", "type": "Data Source"},
                    {"name": "Movement", "type": "Movement"},
                    {"name": "Multi-GAAP", "type": "Multi-GAAP"},
                ],
                "note": "Standard FCCS dimensions (endpoint not available)"
            }
        else:
            # Standard Planning dimensions
            return {
                "items": [
                    {"name": "Years", "type": "Time"},
                    {"name": "Period", "type": "Time"},
                    {"name": "Scenario", "type": "Scenario"},
                    {"name": "Version", "type": "Version"},
                    {"name": "Entity", "type": "Entity"},
                    {"name": "Account", "type": "Account"},
                    {"name": "CostCenter", "type": "CostCenter"},
                    {"name": "Region", "type": "Region"},
                ],
                "note": "Standard Planning dimensions (endpoint not available)"
            }

    async def get_members(
        self,
        app_name: str,
        dimension_name: str
    ) -> dict[str, Any]:
        """Get dimension members / Obter membros da dimensao."""
        if self.config.planning_mock_mode:
            return MOCK_MEMBERS

        # First, try to load from local cache
        cached_members = load_members_from_cache(app_name, dimension_name)
        if cached_members is not None:
            return cached_members

        # If not in cache, try API endpoints
        endpoints = [
            f"/{app_name}/dimensions/{dimension_name}/members{self._get_query_params()}",
            f"/{app_name}/dimensions/{dimension_name}/members",
            f"/{app_name}/metadata/dimensions/{dimension_name}/members{self._get_query_params()}",
            f"/{app_name}/metadata/dimensions/{dimension_name}/members",
            f"/{app_name}/dimensions/{dimension_name}{self._get_query_params()}",
            f"/{app_name}/dimensions/{dimension_name}",
        ]

        for endpoint in endpoints:
            try:
                response = await self._client.get(endpoint)
                if response.status_code == 200:
                    members = response.json()
                    # Save to cache for future use
                    save_members_to_cache(app_name, dimension_name, members)
                    return members
            except Exception:
                continue

        raise ValueError(f"Could not retrieve members for dimension: {dimension_name}")

    async def get_member(
        self,
        app_name: str,
        dimension_name: str,
        member_name: str,
        expansion: Optional[str] = None
    ) -> dict[str, Any]:
        """Get a specific member by name from a dimension / Obter um membro especifico."""
        if self.config.planning_mock_mode:
            return MOCK_MEMBER

        # Build endpoint with optional expansion
        endpoint = f"/{app_name}/dimensions/{dimension_name}/members/{quote(member_name)}"
        if expansion:
            endpoint += f"?expansion={expansion}"
        endpoint += self._get_query_params(bool(expansion))

        response = await self._client.get(endpoint)
        response.raise_for_status()
        return response.json()

    # ========== Data Methods ==========

    async def export_data_slice(
        self,
        app_name: str,
        plan_type: str,
        grid_definition: dict[str, Any]
    ) -> dict[str, Any]:
        """Export data slice / Exportar fatia de dados."""
        if self.config.planning_mock_mode:
            return MOCK_DATA_SLICE

        payload = {"gridDefinition": grid_definition}

        response = await self._client.post(
            f"/{app_name}/plantypes/{plan_type}/exportdataslice{self._get_query_params()}",
            json=payload
        )
        if not response.is_success:
            error_text = await response.aread()
            f"HTTP {response.status_code}: {error_text.decode('utf-8', errors='ignore')}"
            response.raise_for_status()  # This will raise, but we've captured the error
        return response.json()

    async def copy_data(
        self,
        app_name: str,
        parameters: dict[str, Any]
    ) -> dict[str, Any]:
        """Copy data / Copiar dados."""
        if self.config.planning_mock_mode:
            return {"jobId": "401", "status": "Submitted", "jobType": "CopyData"}

        payload = {"jobType": "COPYDATA", **parameters}
        response = await self._client.post(
            f"/{app_name}/jobs{self._get_query_params()}",
            json=payload
        )
        response.raise_for_status()
        return response.json()

    async def clear_data(
        self,
        app_name: str,
        parameters: dict[str, Any]
    ) -> dict[str, Any]:
        """Clear data / Limpar dados."""
        if self.config.planning_mock_mode:
            return {"jobId": "402", "status": "Submitted", "jobType": "ClearData"}

        payload = {"jobType": "CLEARDATA", **parameters}
        response = await self._client.post(
            f"/{app_name}/jobs{self._get_query_params()}",
            json=payload
        )
        response.raise_for_status()
        return response.json()

    # ========== Substitution Variables Methods ==========

    async def get_substitution_variables(
        self,
        app_name: str
    ) -> dict[str, Any]:
        """Get substitution variables / Obter variaveis de substituicao."""
        if self.config.planning_mock_mode:
            return MOCK_SUBSTITUTION_VARIABLES

        response = await self._client.get(
            f"/{app_name}/substitutionvariables{self._get_query_params()}"
        )
        response.raise_for_status()
        return response.json()

    async def set_substitution_variable(
        self,
        app_name: str,
        variable_name: str,
        value: str,
        plan_type: Optional[str] = None
    ) -> dict[str, Any]:
        """Set substitution variable / Definir variavel de substituicao."""
        if self.config.planning_mock_mode:
            return {
                "name": variable_name,
                "value": value,
                "planType": plan_type,
                "status": "Updated"
            }

        payload = {"value": value}
        if plan_type:
            payload["planType"] = plan_type

        response = await self._client.put(
            f"/{app_name}/substitutionvariables/{quote(variable_name)}{self._get_query_params()}",
            json=payload
        )
        response.raise_for_status()
        return response.json()

    # ========== Documents Methods ==========

    async def get_documents(
        self,
        app_name: str
    ) -> dict[str, Any]:
        """Get library documents / Obter documentos da biblioteca."""
        if self.config.planning_mock_mode:
            return MOCK_DOCUMENTS

        response = await self._client.get(
            f"/{app_name}/documents{self._get_query_params()}"
        )
        response.raise_for_status()
        return response.json()

    # ========== Snapshots Methods ==========

    async def get_snapshots(self) -> dict[str, Any]:
        """Get application snapshots / Obter snapshots da aplicacao."""
        if self.config.planning_mock_mode:
            return MOCK_SNAPSHOTS

        # Snapshots are at instance level, not app level
        # Need to use a different base URL or endpoint
        # For now, return mock data
        return MOCK_SNAPSHOTS


