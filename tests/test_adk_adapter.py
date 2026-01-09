"""Tests for the ADK adapter module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from planning_agent.pipeline.adk_adapter import (
    _convert_json_schema_type,
    _convert_schema_to_gemini,
    _tool_catalog_to_function_declarations,
    _find_genai_module,
    AdkAdapter,
    load_adk_adapter,
)
from planning_agent.pipeline.types import Plan, PlanStep


class TestConvertJsonSchemaType:
    """Tests for _convert_json_schema_type function."""

    def test_string_type(self):
        assert _convert_json_schema_type("string") == "STRING"

    def test_number_type(self):
        assert _convert_json_schema_type("number") == "NUMBER"

    def test_integer_type(self):
        assert _convert_json_schema_type("integer") == "INTEGER"

    def test_boolean_type(self):
        assert _convert_json_schema_type("boolean") == "BOOLEAN"

    def test_array_type(self):
        assert _convert_json_schema_type("array") == "ARRAY"

    def test_object_type(self):
        assert _convert_json_schema_type("object") == "OBJECT"

    def test_unknown_type_defaults_to_string(self):
        assert _convert_json_schema_type("unknown") == "STRING"

    def test_union_type_with_null(self):
        # ["string", "null"] should return "STRING"
        assert _convert_json_schema_type(["string", "null"]) == "STRING"

    def test_union_type_null_first(self):
        # ["null", "integer"] should return "INTEGER"
        assert _convert_json_schema_type(["null", "integer"]) == "INTEGER"

    def test_union_type_only_null(self):
        # ["null"] should return "STRING" as fallback
        assert _convert_json_schema_type(["null"]) == "STRING"


class TestConvertSchemaToGemini:
    """Tests for _convert_schema_to_gemini function."""

    def test_empty_schema(self):
        assert _convert_schema_to_gemini({}) == {}

    def test_simple_string_schema(self):
        schema = {"type": "string", "description": "A name"}
        result = _convert_schema_to_gemini(schema)
        assert result == {"type": "STRING", "description": "A name"}

    def test_schema_with_enum(self):
        schema = {"type": "string", "enum": ["a", "b", "c"]}
        result = _convert_schema_to_gemini(schema)
        assert result == {"type": "STRING", "enum": ["a", "b", "c"]}

    def test_object_schema_with_properties(self):
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
            "required": ["name"],
        }
        result = _convert_schema_to_gemini(schema)
        assert result["type"] == "OBJECT"
        assert result["properties"]["name"]["type"] == "STRING"
        assert result["properties"]["age"]["type"] == "INTEGER"
        assert result["required"] == ["name"]

    def test_array_schema_with_items(self):
        schema = {
            "type": "array",
            "items": {"type": "string"},
        }
        result = _convert_schema_to_gemini(schema)
        assert result["type"] == "ARRAY"
        assert result["items"]["type"] == "STRING"

    def test_nested_object_schema(self):
        schema = {
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "properties": {
                        "email": {"type": "string"},
                    },
                },
            },
        }
        result = _convert_schema_to_gemini(schema)
        assert result["properties"]["user"]["type"] == "OBJECT"
        assert result["properties"]["user"]["properties"]["email"]["type"] == "STRING"


class TestToolCatalogToFunctionDeclarations:
    """Tests for _tool_catalog_to_function_declarations function."""

    def test_empty_catalog(self):
        assert _tool_catalog_to_function_declarations([]) == []

    def test_tool_without_name_skipped(self):
        catalog = [{"description": "No name tool"}]
        assert _tool_catalog_to_function_declarations(catalog) == []

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
        result = _tool_catalog_to_function_declarations(catalog)
        assert len(result) == 1
        assert result[0]["name"] == "get_applications"
        assert result[0]["description"] == "Get list of applications"

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
        result = _tool_catalog_to_function_declarations(catalog)
        assert len(result) == 1
        assert "parameters" in result[0]
        assert result[0]["parameters"]["properties"]["dimension"]["type"] == "STRING"

    def test_multiple_tools(self):
        catalog = [
            {"name": "tool1", "description": "First tool", "inputSchema": {"type": "object"}},
            {"name": "tool2", "description": "Second tool", "inputSchema": {"type": "object"}},
        ]
        result = _tool_catalog_to_function_declarations(catalog)
        assert len(result) == 2
        assert result[0]["name"] == "tool1"
        assert result[1]["name"] == "tool2"


class TestAdkAdapter:
    """Tests for AdkAdapter class."""

    def test_init(self):
        adapter = AdkAdapter("google.genai", "gemini-2.0-flash", "test-api-key")
        assert adapter.module_name == "google.genai"
        assert adapter.model_id == "gemini-2.0-flash"
        assert adapter.api_key == "test-api-key"
        assert adapter._client is None

    def test_init_without_api_key(self):
        adapter = AdkAdapter("google.genai", "gemini-2.0-flash", None)
        assert adapter.api_key is None

    @pytest.mark.asyncio
    async def test_plan_without_api_key(self):
        adapter = AdkAdapter("google.genai", "gemini-2.0-flash", None)
        adapter._genai_available = True  # Simulate genai available

        result = await adapter.plan("test query", [])

        assert isinstance(result, Plan)
        assert result.query == "test query"
        assert result.steps == []
        assert "missing API key" in result.notes

    @pytest.mark.asyncio
    async def test_plan_without_genai(self):
        adapter = AdkAdapter("google.genai", "gemini-2.0-flash", "test-key")
        adapter._genai_available = False  # Simulate genai not available

        result = await adapter.plan("test query", [])

        assert isinstance(result, Plan)
        assert result.steps == []
        assert "google.genai module" in result.notes

    @pytest.mark.asyncio
    async def test_plan_empty_tool_catalog(self):
        adapter = AdkAdapter("google.genai", "gemini-2.0-flash", "test-key")
        adapter._genai_available = True

        # Mock the google.genai imports
        with patch.dict('sys.modules', {
            'google.genai': MagicMock(),
            'google.genai.types': MagicMock(),
        }):
            result = await adapter.plan("test query", [])

        assert result.steps == []
        assert "No valid tools in catalog" in result.notes

    @pytest.mark.asyncio
    async def test_plan_with_mock_gemini_response(self):
        adapter = AdkAdapter("google.genai", "gemini-2.0-flash", "test-key")
        adapter._genai_available = True

        # Create mock response
        mock_function_call = MagicMock()
        mock_function_call.name = "get_applications"
        mock_function_call.args = {"filter": "active"}

        mock_part = MagicMock()
        mock_part.text = "I will get the applications"
        mock_part.function_call = mock_function_call

        mock_content = MagicMock()
        mock_content.parts = [mock_part]

        mock_candidate = MagicMock()
        mock_candidate.content = mock_content

        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]

        # Mock client
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
        adapter._client = mock_client

        # Mock google.genai.types
        mock_types = MagicMock()
        mock_types.GenerateContentConfig = MagicMock
        mock_types.Tool = MagicMock
        mock_types.FunctionDeclaration = MagicMock
        mock_types.Content = MagicMock
        mock_types.Part = MagicMock

        with patch.dict('sys.modules', {'google.genai.types': mock_types}):
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
        assert result.notes == "gemini_function_calling"


class TestLoadAdkAdapter:
    """Tests for load_adk_adapter function."""

    def test_load_when_genai_available(self):
        with patch('planning_agent.pipeline.adk_adapter._find_genai_module', return_value=True):
            with patch('planning_agent.pipeline.adk_adapter._find_adk_module', return_value=None):
                adapter = load_adk_adapter("gemini-2.0-flash", "test-key")

        assert adapter is not None
        assert isinstance(adapter, AdkAdapter)
        assert adapter.model_id == "gemini-2.0-flash"
        assert adapter.api_key == "test-key"

    def test_load_when_genai_not_available(self):
        with patch('planning_agent.pipeline.adk_adapter._find_genai_module', return_value=False):
            adapter = load_adk_adapter("gemini-2.0-flash", "test-key")

        assert adapter is None

    def test_load_with_adk_module(self):
        with patch('planning_agent.pipeline.adk_adapter._find_genai_module', return_value=True):
            with patch('planning_agent.pipeline.adk_adapter._find_adk_module', return_value="google.adk"):
                adapter = load_adk_adapter("gemini-2.0-flash", "test-key")

        assert adapter is not None
        assert adapter.module_name == "google.adk"


class TestIntegration:
    """Integration tests for the adapter (require google.genai to be installed)."""

    @pytest.mark.skipif(not _find_genai_module(), reason="google.genai not installed")
    def test_real_module_detection(self):
        """Test that we can detect the real google.genai module."""
        assert _find_genai_module() is True

    @pytest.mark.skipif(not _find_genai_module(), reason="google.genai not installed")
    def test_real_adapter_creation(self):
        """Test creating a real adapter (without API key)."""
        adapter = load_adk_adapter("gemini-2.0-flash", None)
        assert adapter is not None
        assert adapter.model_id == "gemini-2.0-flash"
