"""Google ADK/Gemini adapter for Planning agent planning.

Uses Google's Generative AI (google.genai) to analyze queries and
generate execution plans by leveraging function calling capabilities.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import sys
from typing import Any

from planning_agent.pipeline.types import Plan, PlanStep


ADK_MODULE_CANDIDATES = ["google.adk", "google_adk", "adk"]
GENAI_MODULE = "google.genai"

# Planning system prompt for Gemini
PLANNING_SYSTEM_PROMPT = """You are an intelligent Oracle EPM Planning (EPBCS) assistant.

Your task is to analyze the user's query and select the appropriate tools to fulfill their request.

Key concepts for Oracle Planning:
- PlanApp has 10 dimensions: Years, Period, Scenario, Version, Currency, Entity, CostCenter, Future1, Region, Account
- Common entities: E501 (Chicago), E100 (Lotte), E500 (L7), E800 (Signiel)
- Common accounts: 400000 (Total Revenue), 410000 (Rooms), 420000 (F&B), 710xxx (OPEX)
- Scenarios: Actual, Forecast
- Plan types: FinPlan, FinRPT

Guidelines:
1. Analyze the user's intent carefully
2. Select only the tools that are necessary to complete the task
3. If multiple tools are needed, call them in the order they should be executed
4. Provide clear reasoning for each tool selection
5. Use the exact parameter names and types expected by each tool

If the query is unclear or cannot be handled by the available tools, do not call any functions.
Instead, explain what additional information is needed."""


def _find_adk_module() -> str | None:
    for module_name in ADK_MODULE_CANDIDATES:
        if importlib.util.find_spec(module_name) is not None:
            return module_name
    return None


def _find_genai_module() -> bool:
    return importlib.util.find_spec(GENAI_MODULE) is not None


def _convert_json_schema_type(json_type: str | list) -> str:
    """Convert JSON Schema type to Gemini type."""
    # Handle union types (e.g., ["string", "null"])
    if isinstance(json_type, list):
        # Filter out null and take the first non-null type
        non_null_types = [t for t in json_type if t != "null"]
        if non_null_types:
            json_type = non_null_types[0]
        else:
            return "STRING"

    type_mapping = {
        "string": "STRING",
        "number": "NUMBER",
        "integer": "INTEGER",
        "boolean": "BOOLEAN",
        "array": "ARRAY",
        "object": "OBJECT",
    }
    return type_mapping.get(json_type, "STRING")


def _convert_schema_to_gemini(schema: dict) -> dict:
    """Convert JSON Schema to Gemini Schema format."""
    if not schema:
        return {}

    result = {}
    schema_type = schema.get("type")

    if schema_type:
        result["type"] = _convert_json_schema_type(schema_type)

    if "description" in schema:
        result["description"] = schema["description"]

    if "enum" in schema:
        result["enum"] = schema["enum"]

    # Handle object properties
    if schema_type == "object" and "properties" in schema:
        result["properties"] = {}
        for prop_name, prop_schema in schema["properties"].items():
            result["properties"][prop_name] = _convert_schema_to_gemini(prop_schema)

        if "required" in schema:
            result["required"] = schema["required"]

    # Handle array items
    if schema_type == "array" and "items" in schema:
        result["items"] = _convert_schema_to_gemini(schema["items"])

    return result


def _tool_catalog_to_function_declarations(tool_catalog: list[dict]) -> list[dict]:
    """Convert MCP tool catalog to Gemini FunctionDeclaration format."""
    declarations = []

    for tool in tool_catalog:
        name = tool.get("name", "")
        description = tool.get("description", "")
        input_schema = tool.get("inputSchema", {})

        # Skip tools without proper schema
        if not name:
            continue

        declaration = {
            "name": name,
            "description": description,
        }

        # Convert parameters schema
        if input_schema and input_schema.get("type") == "object":
            parameters = _convert_schema_to_gemini(input_schema)
            if parameters:
                declaration["parameters"] = parameters

        declarations.append(declaration)

    return declarations


class AdkAdapter:
    """Adapter for Google Gemini-based planning.

    Uses Google's Generative AI (google.genai) to analyze queries and
    generate execution plans by leveraging function calling capabilities.
    """

    def __init__(self, module_name: str, model_id: str, api_key: str | None):
        self.module_name = module_name
        self.model_id = model_id
        self.api_key = api_key
        self._client = None
        self._genai_available = _find_genai_module()

        # Import ADK module for reference (optional)
        try:
            self.module = importlib.import_module(module_name)
        except ImportError:
            self.module = None

    def _get_client(self):
        """Lazily initialize the Gemini client."""
        if self._client is None:
            if not self._genai_available:
                raise RuntimeError("google.genai module not available")
            if not self.api_key:
                raise RuntimeError("Google API key not configured")

            from google.genai import Client
            self._client = Client(api_key=self.api_key)

        return self._client

    async def plan(self, query: str, tool_catalog: list[dict]) -> Plan:
        """Generate an execution plan using Gemini's function calling.

        Args:
            query: The user's natural language query.
            tool_catalog: List of available tool definitions (MCP format).

        Returns:
            Plan object with steps to execute.
        """
        # If no API key or genai not available, return empty plan
        if not self.api_key or not self._genai_available:
            return Plan(
                query=query,
                steps=[],
                notes="ADK planning unavailable: missing API key or google.genai module"
            )

        try:
            from google.genai.types import (
                GenerateContentConfig,
                Tool,
                FunctionDeclaration,
                Content,
                Part,
            )

            client = self._get_client()

            # Convert tool catalog to Gemini format
            function_declarations = _tool_catalog_to_function_declarations(tool_catalog)

            if not function_declarations:
                return Plan(
                    query=query,
                    steps=[],
                    notes="No valid tools in catalog"
                )

            # Create Gemini Tool with function declarations
            tools = [Tool(function_declarations=[
                FunctionDeclaration(**decl) for decl in function_declarations
            ])]

            # Create content with system prompt and user query
            contents = [
                Content(
                    role="user",
                    parts=[Part(text=f"{PLANNING_SYSTEM_PROMPT}\n\nUser Query: {query}")]
                )
            ]

            # Generate content with function calling
            response = await client.aio.models.generate_content(
                model=self.model_id,
                contents=contents,
                config=GenerateContentConfig(
                    tools=tools,
                    temperature=0.1,  # Low temperature for consistent planning
                )
            )

            # Parse function calls from response
            steps = []
            rationale_parts = []

            if response.candidates:
                for candidate in response.candidates:
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            # Extract text as rationale
                            if hasattr(part, 'text') and part.text:
                                rationale_parts.append(part.text)

                            # Extract function calls as plan steps
                            if hasattr(part, 'function_call') and part.function_call:
                                fc = part.function_call
                                # Convert args to dict
                                args = {}
                                if fc.args:
                                    # fc.args is typically a dict-like object
                                    args = dict(fc.args) if hasattr(fc.args, 'items') else fc.args

                                steps.append(PlanStep(
                                    tool_name=fc.name,
                                    arguments=args,
                                    rationale=" ".join(rationale_parts) if rationale_parts else "Gemini function call"
                                ))

            notes = "gemini_function_calling"
            if rationale_parts and not steps:
                # Model provided text but no function calls
                notes = f"no_function_calls: {' '.join(rationale_parts)[:200]}"

            return Plan(
                query=query,
                steps=steps,
                notes=notes
            )

        except Exception as e:
            print(f"[AdkAdapter] Planning error: {e}", file=sys.stderr)
            return Plan(
                query=query,
                steps=[],
                notes=f"planning_error: {str(e)[:100]}"
            )


def load_adk_adapter(model_id: str, api_key: str | None) -> AdkAdapter | None:
    """Load the ADK adapter if google.genai is available.

    Args:
        model_id: The Gemini model ID to use (e.g., 'gemini-2.0-flash').
        api_key: Google API key for authentication.

    Returns:
        AdkAdapter instance or None if dependencies unavailable.
    """
    # Check for google.genai (required for planning)
    if not _find_genai_module():
        return None

    # ADK module is optional (we primarily use genai)
    module_name = _find_adk_module()
    if module_name is None:
        module_name = "google.genai"  # Fallback to genai module name

    return AdkAdapter(module_name, model_id, api_key)
