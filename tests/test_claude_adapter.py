"""Tests for the Claude adapter module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import importlib.util

from planning_agent.pipeline.claude_adapter import (
    _convert_json_schema_to_claude_type,
    _build_tool_input_schema,
    _tool_catalog_to_claude_tools,
    _find_claude_sdk,
    ClaudeAdapter,
    load_claude_adapter,
)
from planning_agent.pipeline.types import Plan, PlanStep


class TestConvertJsonSchemaToClaudeType:
    """Tests for _convert_json_schema_to_claude_type function."""

    def test_string_type(self):
        assert _convert_json_schema_to_claude_type("string") == str

    def test_number_type(self):
        assert _convert_json_schema_to_claude_type("number") == float

    def test_integer_type(self):
        assert _convert_json_schema_to_claude_type("integer") == int

    def test_boolean_type(self):
        assert _convert_json_schema_to_claude_type("boolean") == bool

    def test_array_type(self):
        assert _convert_json_schema_to_claude_type("array") == list

    def test_object_type(self):
        assert _convert_json_schema_to_claude_type("object") == dict

    def test_unknown_type_defaults_to_string(self):
        assert _convert_json_schema_to_claude_type("unknown") == str

    def test_union_type_with_null(self):
        # ["string", "null"] should return str
        assert _convert_json_schema_to_claude_type(["string", "null"]) == str

    def test_union_type_null_first(self):
        # ["null", "integer"] should return int
        assert _convert_json_schema_to_claude_type(["null", "integer"]) == int

    def test_union_type_only_null(self):
        # ["null"] should return str as fallback
        assert _convert_json_schema_to_claude_type(["null"]) == str


class TestBuildToolInputSchema:
    """Tests for _build_tool_input_schema function."""

    def test_empty_schema(self):
        assert _build_tool_input_schema({}) == {}

    def test_non_object_schema(self):
        assert _build_tool_input_schema({"type": "string"}) == {}

    def test_object_schema_no_properties(self):
        assert _build_tool_input_schema({"type": "object"}) == {}

    def test_simple_object_schema(self):
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
        }
        result = _build_tool_input_schema(schema)
        assert result == {"name": str, "age": int}

    def test_schema_with_various_types(self):
        schema = {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "count": {"type": "integer"},
                "price": {"type": "number"},
                "active": {"type": "boolean"},
                "tags": {"type": "array"},
                "metadata": {"type": "object"},
            },
        }
        result = _build_tool_input_schema(schema)
        assert result == {
            "text": str,
            "count": int,
            "price": float,
            "active": bool,
            "tags": list,
            "metadata": dict,
        }


class TestToolCatalogToClaudeTools:
    """Tests for _tool_catalog_to_claude_tools function."""

    def test_empty_catalog(self):
        assert _tool_catalog_to_claude_tools([]) == []

    def test_tool_without_name_skipped(self):
        catalog = [{"description": "No name tool"}]
        assert _tool_catalog_to_claude_tools(catalog) == []

    def test_simple_tool(self):
        catalog = [
            {
                "name": "get_applications",
                "description": "Get list of applications",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            }
        ]
        result = _tool_catalog_to_claude_tools(catalog)
        assert len(result) == 1
        assert result[0]["name"] == "get_applications"
        assert result[0]["description"] == "Get list of applications"
        assert result[0]["schema"] == {}

    def test_tool_with_parameters(self):
        catalog = [
            {
                "name": "get_dimension_members",
                "description": "Get dimension members",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "dimension": {"type": "string", "description": "Dimension name"},
                        "limit": {"type": "integer"},
                    },
                    "required": ["dimension"],
                },
            }
        ]
        result = _tool_catalog_to_claude_tools(catalog)
        assert len(result) == 1
        assert result[0]["schema"]["dimension"] == str
        assert result[0]["schema"]["limit"] == int

    def test_multiple_tools(self):
        catalog = [
            {"name": "tool1", "description": "First tool", "inputSchema": {"type": "object"}},
            {"name": "tool2", "description": "Second tool", "inputSchema": {"type": "object"}},
        ]
        result = _tool_catalog_to_claude_tools(catalog)
        assert len(result) == 2
        assert result[0]["name"] == "tool1"
        assert result[1]["name"] == "tool2"


class TestClaudeAdapter:
    """Tests for ClaudeAdapter class."""

    def test_init(self):
        adapter = ClaudeAdapter("claude-sonnet-4-20250514", "test-api-key")
        assert adapter.model == "claude-sonnet-4-20250514"
        assert adapter.api_key == "test-api-key"
        assert adapter._client is None

    def test_init_without_api_key(self):
        adapter = ClaudeAdapter("claude-sonnet-4-20250514", None)
        assert adapter.api_key is None

    def test_is_available_with_key(self):
        adapter = ClaudeAdapter("claude-sonnet-4-20250514", "test-key")
        adapter._sdk_available = True
        assert adapter.is_available is True

    def test_is_available_without_key(self):
        adapter = ClaudeAdapter("claude-sonnet-4-20250514", None)
        adapter._sdk_available = True
        assert adapter.is_available is False

    def test_is_available_without_sdk(self):
        adapter = ClaudeAdapter("claude-sonnet-4-20250514", "test-key")
        adapter._sdk_available = False
        assert adapter.is_available is False

    @pytest.mark.asyncio
    async def test_plan_without_api_key(self):
        adapter = ClaudeAdapter("claude-sonnet-4-20250514", None)
        adapter._sdk_available = True

        result = await adapter.plan("test query", [])

        assert isinstance(result, Plan)
        assert result.query == "test query"
        assert result.steps == []
        assert "missing API key" in result.notes

    @pytest.mark.asyncio
    async def test_plan_without_sdk(self):
        adapter = ClaudeAdapter("claude-sonnet-4-20250514", "test-key")
        adapter._sdk_available = False

        result = await adapter.plan("test query", [])

        assert isinstance(result, Plan)
        assert result.steps == []
        assert "claude_agent_sdk module" in result.notes

    @pytest.mark.asyncio
    async def test_plan_empty_tool_catalog(self):
        adapter = ClaudeAdapter("claude-sonnet-4-20250514", "test-key")
        adapter._sdk_available = True

        # Mock anthropic
        with patch.dict('sys.modules', {
            'anthropic': MagicMock(),
            'claude_agent_sdk': MagicMock(),
        }):
            result = await adapter.plan("test query", [])

        assert result.steps == []
        assert "No valid tools in catalog" in result.notes

    @pytest.mark.asyncio
    async def test_plan_with_mock_claude_response(self):
        adapter = ClaudeAdapter("claude-sonnet-4-20250514", "test-key")
        adapter._sdk_available = True

        # Create mock response
        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = "I will get the applications"

        mock_tool_use_block = MagicMock()
        mock_tool_use_block.type = "tool_use"
        mock_tool_use_block.name = "get_applications"
        mock_tool_use_block.input = {"filter": "active"}

        mock_response = MagicMock()
        mock_response.content = [mock_text_block, mock_tool_use_block]

        # Mock client
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        # Mock anthropic module
        mock_anthropic = MagicMock()
        mock_anthropic.AsyncAnthropic.return_value = mock_client

        with patch.dict('sys.modules', {
            'anthropic': mock_anthropic,
            'claude_agent_sdk': MagicMock(),
        }):
            tool_catalog = [
                {
                    "name": "get_applications",
                    "description": "Get applications",
                    "inputSchema": {"type": "object", "properties": {}},
                }
            ]
            result = await adapter.plan("list all applications", tool_catalog)

        assert isinstance(result, Plan)
        assert result.query == "list all applications"
        assert len(result.steps) == 1
        assert result.steps[0].tool_name == "get_applications"
        assert result.notes == "claude_function_calling"


class TestLoadClaudeAdapter:
    """Tests for load_claude_adapter function."""

    def test_load_when_anthropic_available(self):
        with patch('importlib.util.find_spec', return_value=MagicMock()):
            adapter = load_claude_adapter("claude-sonnet-4-20250514", "test-key")

        assert adapter is not None
        assert isinstance(adapter, ClaudeAdapter)
        assert adapter.model == "claude-sonnet-4-20250514"
        assert adapter.api_key == "test-key"

    def test_load_when_anthropic_not_available(self):
        with patch('importlib.util.find_spec', return_value=None):
            adapter = load_claude_adapter("claude-sonnet-4-20250514", "test-key")

        assert adapter is None


class TestIntegration:
    """Integration tests for the adapter (require anthropic to be installed)."""

    @pytest.mark.skipif(
        importlib.util.find_spec("anthropic") is None,
        reason="anthropic not installed"
    )
    def test_real_module_detection(self):
        """Test that we can detect the real anthropic module."""
        assert importlib.util.find_spec("anthropic") is not None

    @pytest.mark.skipif(
        importlib.util.find_spec("anthropic") is None,
        reason="anthropic not installed"
    )
    def test_real_adapter_creation(self):
        """Test creating a real adapter (without API key)."""
        adapter = load_claude_adapter("claude-sonnet-4-20250514", None)
        assert adapter is not None
        assert adapter.model == "claude-sonnet-4-20250514"
