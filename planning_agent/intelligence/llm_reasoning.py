"""LLM-Powered Reasoning for Planning operations.

Uses Claude/Gemini API for:
- Complex intent classification
- Query understanding and disambiguation
- Response generation
- Error explanation
- Recommendation synthesis
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import json
import os
import asyncio
from enum import Enum

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

from planning_agent.intelligence.intent_classifier import Intent, IntentType


class ReasoningMode(Enum):
    """Reasoning modes for different use cases."""
    INTENT_CLASSIFICATION = "intent_classification"
    QUERY_UNDERSTANDING = "query_understanding"
    ERROR_EXPLANATION = "error_explanation"
    RESPONSE_SYNTHESIS = "response_synthesis"
    RECOMMENDATION = "recommendation"
    DISAMBIGUATION = "disambiguation"


@dataclass
class ReasoningResult:
    """Result from LLM reasoning."""
    success: bool
    content: str
    structured_data: Optional[Dict[str, Any]] = None
    confidence: float = 0.0
    tokens_used: int = 0
    reasoning_mode: ReasoningMode = ReasoningMode.QUERY_UNDERSTANDING


SYSTEM_PROMPTS = {
    ReasoningMode.INTENT_CLASSIFICATION: """You are an expert at understanding Oracle EPM Cloud Planning (EPBCS) queries.

Classify user queries into intents and extract Planning-specific entities (Accounts, Entities, Scenarios, Periods, Versions, Cost Centers, Regions).

Available intents:
- data_retrieval: Retrieving financial data, revenue, expenses, balances
- dimension_exploration: Exploring dimensions, members, hierarchies
- job_management: Checking job status, monitoring tasks
- business_rule: Running calculations or business rules
- reporting: Generating or viewing reports/documents
- variance_analysis: Comparing actual vs forecast/budget, YoY analysis
- data_management: Copying or clearing data
- substitution_variables: Managing substitution variables
- metadata_validation: Validating application metadata
- document_management: Accessing library documents/snapshots

Respond in JSON format only:
{"intent": "intent_name", "confidence": 0.0-1.0, "entities": {}, "suggested_tools": [], "reasoning": "brief"}""",
    
    ReasoningMode.QUERY_UNDERSTANDING: """You are an expert assistant for Oracle EPM Cloud Planning.
Understand user queries and provide clear, structured responses.
Be concise but thorough. Use Planning terminology correctly.""",

    ReasoningMode.ERROR_EXPLANATION: """You are an expert at explaining Oracle EPM Cloud Planning errors.
Identify root cause, explain simply, and suggest resolution steps.""",

    ReasoningMode.RESPONSE_SYNTHESIS: """You are an expert at synthesizing Planning query results.
Summarize key findings, highlight important values, note anomalies, and suggest follow-up actions.""",

    ReasoningMode.RECOMMENDATION: """You are an expert Planning advisor providing recommendations.
Consider context, suggest follow-up actions, highlight best practices.""",

    ReasoningMode.DISAMBIGUATION: """You are an expert at clarifying ambiguous Planning queries.
Identify ambiguity, list interpretations, ask clarifying questions."""
}


TOOL_DESCRIPTIONS = {
    "smart_retrieve": "Retrieve financial data with automatic 10-dimension handling",
    "smart_retrieve_revenue": "Get revenue breakdown (Rooms, F&B, Other)",
    "smart_retrieve_monthly": "Get monthly data for an account",
    "smart_retrieve_variance": "Perform variance analysis (Actual vs Forecast/Prior Year)",
    "export_data_slice": "Export data slice with custom grid definition",
    "get_dimensions": "List all dimensions",
    "get_members": "Get members of a dimension",
    "get_member": "Get details for a specific member",
    "list_jobs": "List recent jobs",
    "get_job_status": "Check status of a specific job",
    "execute_job": "Execute a business rule or task",
    "copy_data": "Copy data between scenarios/years/periods",
    "clear_data": "Clear data for a slice",
    "get_substitution_variables": "List substitution variables",
    "set_substitution_variable": "Update a substitution variable",
    "get_documents": "List library documents",
    "get_snapshots": "List application snapshots",
}


class LLMReasoner:
    """LLM-powered reasoning for complex Planning operations."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 1024,
        temperature: float = 0.3
    ):
        """Initialize LLM reasoner."""
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        
        if HAS_ANTHROPIC and self.api_key:
            self.client = anthropic.Anthropic(api_key=self.api_key)
            self.async_client = anthropic.AsyncAnthropic(api_key=self.api_key)
            self._available = True
        else:
            self.client = None
            self.async_client = None
            self._available = False
    
    @property
    def is_available(self) -> bool:
        """Check if LLM is available."""
        return self._available
    
    async def classify_intent_async(
        self,
        query: str,
        entities: Dict[str, str],
        context: Optional[Dict[str, Any]] = None
    ) -> Intent:
        """Async version of classify_intent."""
        if not self._available:
            return self._fallback_classification(query, entities)
        
        try:
            user_prompt = self._build_classification_prompt(query, entities, context)
            
            response = await self.async_client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=SYSTEM_PROMPTS[ReasoningMode.INTENT_CLASSIFICATION],
                messages=[{"role": "user", "content": user_prompt}]
            )
            
            content = response.content[0].text
            result = self._parse_json_response(content)
            
            if result:
                intent_name = result.get("intent", "unknown")
                intent_type = self._map_intent_type(intent_name)
                
                return Intent(
                    name=intent_name,
                    intent_type=intent_type,
                    confidence=result.get("confidence", 0.8),
                    entities={**entities, **result.get("entities", {})},
                    suggested_tools=result.get("suggested_tools", []),
                    sub_intent=result.get("sub_intent"),
                    reasoning=result.get("reasoning")
                )
            
        except Exception as e:
            print(f"LLM classification error: {e}")
        
        return self._fallback_classification(query, entities)
    
    async def understand_query(
        self,
        query: str,
        context: Dict[str, Any]
    ) -> ReasoningResult:
        """Understand and analyze a user query."""
        if not self._available:
            return ReasoningResult(success=False, content="LLM not available", reasoning_mode=ReasoningMode.QUERY_UNDERSTANDING)
        
        try:
            prompt = f"Analyze this Planning query:\n\nQuery: {query}\n\nCurrent Context:\n{json.dumps(context, indent=2)}\n\nProvide intent analysis and recommended approach."
            response = await self.async_client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=SYSTEM_PROMPTS[ReasoningMode.QUERY_UNDERSTANDING],
                messages=[{"role": "user", "content": prompt}]
            )
            return ReasoningResult(success=True, content=response.content[0].text, tokens_used=response.usage.input_tokens + response.usage.output_tokens, reasoning_mode=ReasoningMode.QUERY_UNDERSTANDING)
        except Exception as e:
            return ReasoningResult(success=False, content=f"Error: {str(e)}", reasoning_mode=ReasoningMode.QUERY_UNDERSTANDING)
    
    async def synthesize_results(
        self,
        results: List[Dict[str, Any]],
        query: str,
        context: Dict[str, Any]
    ) -> ReasoningResult:
        """Synthesize multiple tool results into a coherent response."""
        if not self._available:
            return ReasoningResult(success=False, content="LLM not available for synthesis", reasoning_mode=ReasoningMode.RESPONSE_SYNTHESIS)
        
        try:
            prompt = f"Synthesize these Planning query results:\n\nQuery: {query}\n\nResults:\n{json.dumps(results, indent=2, default=str)}\n\nContext:\n{json.dumps(context, indent=2)}"
            response = await self.async_client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=SYSTEM_PROMPTS[ReasoningMode.RESPONSE_SYNTHESIS],
                messages=[{"role": "user", "content": prompt}]
            )
            return ReasoningResult(success=True, content=response.content[0].text, tokens_used=response.usage.input_tokens + response.usage.output_tokens, reasoning_mode=ReasoningMode.RESPONSE_SYNTHESIS)
        except Exception as e:
            return ReasoningResult(success=False, content=f"Synthesis failed: {str(e)}", reasoning_mode=ReasoningMode.RESPONSE_SYNTHESIS)

    def _build_classification_prompt(self, query: str, entities: Dict[str, str], context: Optional[Dict[str, Any]] = None) -> str:
        prompt_parts = [f"Query: {query}", "", f"Pre-extracted entities: {json.dumps(entities)}"]
        if context:
            pov = context.get("current_pov", {})
            if pov:
                prompt_parts.extend(["", "Current POV context:", f"- Period: {pov.get('period', 'unknown')}", f"- Year: {pov.get('years', 'unknown')}", f"- Scenario: {pov.get('scenario', 'unknown')}", f"- Entity: {pov.get('entity', 'unknown')}"])
        prompt_parts.extend(["", "Available tools:", *[f"- {name}: {desc}" for name, desc in TOOL_DESCRIPTIONS.items()], "", "Classify the intent and respond with JSON only."])
        return "\n".join(prompt_parts)
    
    def _parse_json_response(self, content: str) -> Optional[Dict]:
        try: return json.loads(content)
        except: pass
        import re
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content) or re.search(r'\{[\s\S]*\}', content)
        if json_match:
            try: return json.loads(json_match.group(1 if '```' in json_match.group(0) else 0))
            except: pass
        return None
    
    def _map_intent_type(self, intent_name: str) -> IntentType:
        mapping = {
            "data_retrieval": IntentType.DATA_RETRIEVAL,
            "dimension_exploration": IntentType.DIMENSION_EXPLORATION,
            "job_management": IntentType.JOB_MANAGEMENT,
            "business_rule": IntentType.BUSINESS_RULE,
            "reporting": IntentType.REPORTING,
            "variance_analysis": IntentType.VARIANCE_ANALYSIS,
            "data_management": IntentType.DATA_MANAGEMENT,
            "substitution_variables": IntentType.SUBSTITUTION_VARIABLES,
            "metadata_validation": IntentType.METADATA_VALIDATION,
            "document_management": IntentType.DOCUMENT_MANAGEMENT,
        }
        return mapping.get(intent_name, IntentType.UNKNOWN)
    
    def _fallback_classification(self, query: str, entities: Dict[str, str]) -> Intent:
        query_lower = query.lower()
        if any(kw in query_lower for kw in ["dimension", "member", "hierarchy"]):
            intent_type = IntentType.DIMENSION_EXPLORATION
            tools = ["get_dimensions", "get_members"]
        elif any(kw in query_lower for kw in ["job", "status", "running"]):
            intent_type = IntentType.JOB_MANAGEMENT
            tools = ["list_jobs"]
        elif any(kw in query_lower for kw in ["variance", "compare", "versus"]):
            intent_type = IntentType.VARIANCE_ANALYSIS
            tools = ["smart_retrieve_variance"]
        elif any(kw in query_lower for kw in ["copy", "clear"]):
            intent_type = IntentType.DATA_MANAGEMENT
            tools = ["copy_data"]
        else:
            intent_type = IntentType.DATA_RETRIEVAL
            tools = ["smart_retrieve"]
        
        return Intent(name=intent_type.value, intent_type=intent_type, confidence=0.5, entities=entities, suggested_tools=tools, reasoning="Fallback classification")
