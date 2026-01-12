"""Claude Agent SDK adapter for Planning agent planning.

Uses Anthropic's Claude Agent SDK to analyze queries and
generate execution plans by leveraging function calling capabilities.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from typing import Any

from planning_agent.pipeline.types import Plan, PlanStep


# Check if claude_agent_sdk is available
def _find_claude_sdk() -> bool:
    return importlib.util.find_spec("claude_agent_sdk") is not None


HAS_CLAUDE_SDK = _find_claude_sdk()

# Planning system prompt for Claude
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


def _convert_json_schema_to_claude_type(json_type: str | list) -> type | str:
    """Convert JSON Schema type to Python type for Claude tool definitions."""
    if isinstance(json_type, list):
        non_null_types = [t for t in json_type if t != "null"]
        if non_null_types:
            json_type = non_null_types[0]
        else:
            return str

    type_mapping = {
        "string": str,
        "number": float,
        "integer": int,
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    return type_mapping.get(json_type, str)


def _build_tool_input_schema(input_schema: dict) -> dict:
    """Convert MCP input schema to Claude SDK tool schema format.

    The Claude SDK accepts either:
    - Simple type mapping: {"param": str, "count": int}
    - Full JSON Schema format for complex validation
    """
    if not input_schema or input_schema.get("type") != "object":
        return {}

    properties = input_schema.get("properties", {})
    if not properties:
        return {}

    # Build simple type mapping for Claude SDK
    schema = {}
    for prop_name, prop_def in properties.items():
        prop_type = prop_def.get("type", "string")
        schema[prop_name] = _convert_json_schema_to_claude_type(prop_type)

    return schema


def _tool_catalog_to_claude_tools(tool_catalog: list[dict]) -> list[dict]:
    """Convert MCP tool catalog to Claude SDK tool definitions.

    Returns a list of tool info dicts with name, description, and schema.
    """
    tools = []

    for tool in tool_catalog:
        name = tool.get("name", "")
        description = tool.get("description", "")
        input_schema = tool.get("inputSchema", {})

        if not name:
            continue

        tool_info = {
            "name": name,
            "description": description,
            "schema": _build_tool_input_schema(input_schema),
            "raw_schema": input_schema,  # Keep original for complex cases
        }
        tools.append(tool_info)

    return tools


class ClaudeAdapter:
    """Adapter for Claude Agent SDK-based planning.

    Uses Anthropic's Claude Agent SDK to analyze queries and
    generate execution plans by leveraging function calling capabilities.
    """

    def __init__(self, model: str, api_key: str | None):
        self.model = model
        self.api_key = api_key
        self._client = None
        self._sdk_available = HAS_CLAUDE_SDK

    @property
    def is_available(self) -> bool:
        """Check if the adapter is available for use."""
        return self._sdk_available and bool(self.api_key)

    async def plan(self, query: str, tool_catalog: list[dict]) -> Plan:
        """Generate an execution plan using Claude's function calling.

        Args:
            query: The user's natural language query.
            tool_catalog: List of available tool definitions (MCP format).

        Returns:
            Plan object with steps to execute.
        """
        if not self.api_key or not self._sdk_available:
            return Plan(
                query=query,
                steps=[],
                notes="Claude SDK planning unavailable: missing API key or claude_agent_sdk module"
            )

        try:
            from claude_agent_sdk import (
                ClaudeSDKClient,
                ClaudeAgentOptions,
                AssistantMessage,
                ToolUseBlock,
                TextBlock,
            )

            # Convert tool catalog to Claude format
            claude_tools = _tool_catalog_to_claude_tools(tool_catalog)

            if not claude_tools:
                return Plan(
                    query=query,
                    steps=[],
                    notes="No valid tools in catalog"
                )

            # Build the planning prompt
            tools_description = "\n".join([
                f"- {t['name']}: {t['description']}"
                for t in claude_tools
            ])

            planning_prompt = f"""{PLANNING_SYSTEM_PROMPT}

Available tools:
{tools_description}

User Query: {query}

Analyze this query and determine which tool(s) to call. For each tool you want to call,
respond with a JSON object in the format:
{{"tool": "tool_name", "arguments": {{"param1": "value1", ...}}, "rationale": "why this tool"}}

If multiple tools are needed, provide multiple JSON objects, one per line."""

            # Use Anthropic API directly for planning (simpler than full agent loop)
            # The Claude Agent SDK is mainly for full agent workflows
            # For simple function selection, we can use the anthropic package directly
            import anthropic

            client = anthropic.AsyncAnthropic(api_key=self.api_key)

            # Build tools for Claude API
            api_tools = []
            for tool_info in claude_tools:
                tool_def = {
                    "name": tool_info["name"],
                    "description": tool_info["description"],
                    "input_schema": tool_info["raw_schema"] if tool_info["raw_schema"] else {
                        "type": "object",
                        "properties": {},
                    }
                }
                api_tools.append(tool_def)

            # Call Claude with tools
            response = await client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=PLANNING_SYSTEM_PROMPT,
                tools=api_tools,
                messages=[
                    {"role": "user", "content": query}
                ],
                temperature=0.1,  # Low temperature for consistent planning
            )

            # Parse response for tool calls
            steps = []
            rationale_parts = []

            for block in response.content:
                if block.type == "text":
                    rationale_parts.append(block.text)
                elif block.type == "tool_use":
                    steps.append(PlanStep(
                        tool_name=block.name,
                        arguments=dict(block.input) if block.input else {},
                        rationale=" ".join(rationale_parts) if rationale_parts else "Claude tool selection"
                    ))

            notes = "claude_function_calling"
            if rationale_parts and not steps:
                notes = f"no_function_calls: {' '.join(rationale_parts)[:200]}"

            return Plan(
                query=query,
                steps=steps,
                notes=notes
            )

        except Exception as e:
            print(f"[ClaudeAdapter] Planning error: {e}", file=sys.stderr)
            return Plan(
                query=query,
                steps=[],
                notes=f"planning_error: {str(e)[:100]}"
            )


def load_claude_adapter(model: str, api_key: str | None) -> ClaudeAdapter | None:
    """Load the Claude adapter if dependencies are available.

    Args:
        model: The Claude model ID to use (e.g., 'claude-sonnet-4-20250514').
        api_key: Anthropic API key for authentication.

    Returns:
        ClaudeAdapter instance or None if dependencies unavailable.
    """
    # Check for anthropic package (required for planning)
    if importlib.util.find_spec("anthropic") is None:
        return None

    return ClaudeAdapter(model, api_key)
