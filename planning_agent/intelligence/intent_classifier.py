"""Intent Classification for Planning queries.

Classifies user queries into actionable intents and extracts
Planning-specific entities (periods, scenarios, accounts, entities, etc.).

Supports both rule-based and LLM-powered classification.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import re
from enum import Enum


class IntentType(Enum):
    """Planning Intent Types."""
    DATA_RETRIEVAL = "data_retrieval"
    DIMENSION_EXPLORATION = "dimension_exploration"
    JOB_MANAGEMENT = "job_management"
    BUSINESS_RULE = "business_rule"
    REPORTING = "reporting"
    VARIANCE_ANALYSIS = "variance_analysis"
    DATA_MANAGEMENT = "data_management"  # Copy/Clear
    SUBSTITUTION_VARIABLES = "substitution_variables"
    METADATA_VALIDATION = "metadata_validation"
    DOCUMENT_MANAGEMENT = "document_management"
    UNKNOWN = "unknown"


@dataclass
class Intent:
    """Classified intent with entities and suggested tools."""
    name: str
    intent_type: IntentType
    confidence: float
    entities: Dict[str, str] = field(default_factory=dict)
    suggested_tools: List[str] = field(default_factory=list)
    sub_intent: Optional[str] = None
    reasoning: Optional[str] = None  # For LLM-based classification


@dataclass
class EntityMatch:
    """A matched entity from the query."""
    entity_type: str
    value: str
    start_pos: int
    end_pos: int
    normalized_value: Optional[str] = None


class PlanningIntentClassifier:
    """Classify user queries into Planning intents and extract entities.
    
    Uses a combination of:
    1. Pattern matching for common query structures
    2. Keyword scoring for intent classification
    3. Regex extraction for Planning entities
    4. Optional LLM enhancement for complex queries
    """
    
    # Intent configuration with patterns, keywords, and suggested tools
    INTENT_CONFIG = {
        IntentType.DATA_RETRIEVAL: {
            "patterns": [
                r"(?:get|retrieve|export|show|what is|what's|tell me|give me|fetch).{0,30}(?:data|value|balance|amount|number|revenue|expense)",
                r"(?:revenue|profit|income|expense|asset|liability|equity|cash)",
                r"(?:rooms|f&b|other|total revenue|net income|operating|gross margin)",
                r"(?:how much|what are the).{0,20}(?:for|in|at)",
                r"(?:pull|extract).{0,20}(?:data|numbers|figures)",
            ],
            "keywords": ["data", "value", "balance", "amount", "revenue", "profit", "income", 
                        "expense", "retrieve", "get", "show", "export", "pull", "fetch", "rooms"],
            "negative_keywords": ["job", "status", "dimension", "member", "variable", "document"],
            "tools": ["smart_retrieve", "smart_retrieve_revenue", "smart_retrieve_monthly", "export_data_slice"],
            "sub_intents": {
                "single_value": r"(?:what is|what's|show me).{0,20}(?:the|a)?\s*(?:value|balance|amount)",
                "time_series": r"(?:trend|over time|monthly|quarterly|by period)",
                "revenue_breakdown": r"(?:revenue|rooms|f&b|breakdown)",
            }
        },
        IntentType.DIMENSION_EXPLORATION: {
            "patterns": [
                r"(?:list|show|get|what are).{0,20}(?:dimension|member|hierarchy|entities|accounts|cost centers|regions)",
                r"(?:what|which|how many).{0,20}(?:entities|accounts|members|dimensions|cc|regions)",
                r"(?:children|descendants|parent|ancestors).{0,20}(?:of|for)",
                r"(?:explore|browse|navigate).{0,20}(?:hierarchy|structure|tree)",
            ],
            "keywords": ["dimension", "member", "hierarchy", "entity", "account", "list", 
                        "children", "parent", "structure", "metadata", "cost center", "region"],
            "negative_keywords": ["value", "balance", "data", "job"],
            "tools": ["get_dimensions", "get_members", "get_member"],
            "sub_intents": {
                "list_all": r"(?:all|list all|show all|every)",
                "hierarchy": r"(?:hierarchy|children|parent|structure|tree)",
                "search": r"(?:find|search|look for|where is)",
            }
        },
        IntentType.BUSINESS_RULE: {
            "patterns": [
                r"(?:run|execute|trigger|start).{0,20}(?:rule|business rule|calculation|calc)",
                r"(?:calculate|compute).{0,20}(?:revenue|expense|net income|plan)",
            ],
            "keywords": ["rule", "business rule", "execute", "run", "calculate", "calc", "compute"],
            "negative_keywords": ["job status"],
            "tools": ["execute_job"],
            "sub_intents": {
                "run": r"(?:run|execute|trigger|start)",
            }
        },
        IntentType.JOB_MANAGEMENT: {
            "patterns": [
                r"(?:job|task|process|batch).{0,20}(?:status|running|complete|failed)",
                r"(?:check|monitor|track|what happened).{0,20}(?:job|task|process)",
                r"(?:list|show|get).{0,20}(?:job|task|recent job)",
                r"(?:is the|did the).{0,20}(?:job|rule|process).{0,20}(?:finish|complete|fail)",
            ],
            "keywords": ["job", "task", "process", "status", "running", "complete", 
                        "failed", "monitor", "check", "batch"],
            "negative_keywords": ["data"],
            "tools": ["list_jobs", "get_job_status"],
            "sub_intents": {
                "status": r"(?:status|progress|state|how is)",
                "list": r"(?:list|show|recent|all)",
            }
        },
        IntentType.VARIANCE_ANALYSIS: {
            "patterns": [
                r"(?:variance|var|difference|delta|change)",
                r"(?:actual|forecast|budget).{0,20}(?:vs|versus|against|compared)",
                r"(?:compare|comparison).{0,20}(?:actual|forecast|budget|prior)",
                r"(?:year over year|yoy|month over month|mom|period over period)",
            ],
            "keywords": ["variance", "compare", "comparison", "versus", "vs", "actual", 
                        "forecast", "budget", "yoy", "mom", "delta", "change"],
            "negative_keywords": [],
            "tools": ["smart_retrieve_variance", "smart_retrieve"],
            "sub_intents": {
                "actual_vs_forecast": r"(?:actual).{0,10}(?:vs|versus|forecast)",
                "yoy": r"(?:year over year|yoy|prior year|py)",
            }
        },
        IntentType.DATA_MANAGEMENT: {
            "patterns": [
                r"(?:copy|clear|delete|move).{0,20}(?:data|numbers|figures|plan)",
                r"(?:copy from).{0,20}(?:to)",
                r"(?:wipe|clean|reset).{0,20}(?:scenario|period|year)",
            ],
            "keywords": ["copy", "clear", "delete", "move", "wipe", "clean", "reset"],
            "negative_keywords": [],
            "tools": ["copy_data", "clear_data"],
            "sub_intents": {
                "copy": r"(?:copy|move)",
                "clear": r"(?:clear|delete|wipe|reset)",
            }
        },
        IntentType.SUBSTITUTION_VARIABLES: {
            "patterns": [
                r"(?:variable|sub var|substitution variable)",
                r"(?:set|update|change).{0,20}(?:variable|value)",
                r"(?:get|list|show).{0,20}(?:variable|vars)",
            ],
            "keywords": ["variable", "sub var", "substitution", "set", "update"],
            "negative_keywords": [],
            "tools": ["get_substitution_variables", "set_substitution_variable"],
        },
        IntentType.DOCUMENT_MANAGEMENT: {
            "patterns": [
                r"(?:document|file|library|folder|report file)",
                r"(?:list|show|get).{0,20}(?:document|file|library)",
            ],
            "keywords": ["document", "file", "library", "folder"],
            "negative_keywords": [],
            "tools": ["get_documents"],
        },
    }
    
    # Planning Entity patterns with normalization
    ENTITY_PATTERNS = {
        "period": {
            "pattern": r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|Q[1-4]|YearTotal|BegBal)\b",
            "normalize": lambda x: x.capitalize() if len(x) == 3 else x
        },
        "year": {
            "pattern": r"\b(FY\d{2}|\d{4})\b",
            "normalize": lambda x: f"FY{x[-2:]}" if x.isdigit() else x.upper()
        },
        "scenario": {
            "pattern": r"\b(Actual|Forecast|Budget|Plan|Working|Final)\b",
            "normalize": lambda x: x.capitalize()
        },
        "account": {
            # Match Planning account patterns (usually 6 digits or descriptive)
            "pattern": r"\b(\d{5,6}|[4-9]\d{5}|Total[\s_]Revenue|Rooms|F&B|Net[\s_]Income|Operating[\s_]Expenses)\b",
            "normalize": lambda x: x.replace("_", " ").strip()
        },
        "entity": {
            # Match Planning entity patterns (e.g., E501, E100, etc)
            "pattern": r"\b(E\d{3,4}|All[\s_]Entity|Total[\s_]Geography)\b",
            "normalize": lambda x: x.replace("_", " ").upper()
        },
        "cost_center": {
            "pattern": r"\b(CC\d{4}|No[\s_]CostCenter)\b",
            "normalize": lambda x: x.replace("_", "").upper()
        },
        "region": {
            "pattern": r"\b(R\d{3}|All[\s_]Region)\b",
            "normalize": lambda x: x.replace("_", "").upper()
        },
        "version": {
            "pattern": r"\b(Final|Working|Draft|Version\d)\b",
            "normalize": lambda x: x.capitalize()
        },
        "currency": {
            "pattern": r"\b(USD|EUR|GBP|JPY|BRL|Local|Reporting)\b",
            "normalize": lambda x: x.upper()
        },
        "job_id": {
            "pattern": r"\b(\d{8,})\b",
            "normalize": lambda x: x
        },
    }
    
    # Common Planning abbreviations and aliases
    ALIASES = {
        # Periods
        "january": "Jan", "february": "Feb", "march": "Mar", "april": "Apr",
        "may": "May", "june": "Jun", "july": "Jul", "august": "Aug",
        "september": "Sep", "october": "Oct", "november": "Nov", "december": "Dec",
        "q1": "Q1", "q2": "Q2", "q3": "Q3", "q4": "Q4",
        "year total": "YearTotal", "full year": "YearTotal", "annual": "YearTotal",
        # Scenarios
        "actuals": "Actual", "act": "Actual", "forecast": "Forecast", "fcst": "Forecast",
        "plan": "Plan", "budget": "Budget", "bud": "Budget",
        # Common accounts
        "net income": "Net Income", "ni": "Net Income",
        "total revenue": "400000", "revenue": "400000",
        "rooms revenue": "410000", "rooms": "410000",
        "f&b revenue": "420000", "f&b": "420000", "food and beverage": "420000",
        "operating expenses": "600000", "opex": "600000",
        # Versions
        "final version": "Final", "working version": "Working",
    }
    
    def __init__(self, use_llm: bool = False):
        """Initialize classifier."""
        self.use_llm = use_llm
        self._llm_reasoner = None
        
        # Compile regex patterns for performance
        self._compiled_patterns = {}
        for intent_type, config in self.INTENT_CONFIG.items():
            self._compiled_patterns[intent_type] = [
                re.compile(p, re.IGNORECASE) for p in config["patterns"]
            ]
        
        self._compiled_entity_patterns = {
            entity_type: re.compile(config["pattern"], re.IGNORECASE)
            for entity_type, config in self.ENTITY_PATTERNS.items()
        }
    
    def set_llm_reasoner(self, reasoner):
        """Set LLM reasoner for enhanced classification."""
        self._llm_reasoner = reasoner
        self.use_llm = True
    
    def classify(self, query: str) -> Intent:
        """Classify user query into intent with entities."""
        processed_query = self._preprocess_query(query)
        entities = self.extract_entities(processed_query)
        intent_scores = self._score_intents(processed_query, entities)
        
        best_intent_type, best_score = max(intent_scores.items(), key=lambda x: x[1])
        
        if best_score < 0.3 and self.use_llm and self._llm_reasoner:
            return self._classify_with_llm(query, entities)
        
        sub_intent = self._detect_sub_intent(processed_query, best_intent_type)
        config = self.INTENT_CONFIG.get(best_intent_type, {})
        suggested_tools = config.get("tools", [])
        
        return Intent(
            name=best_intent_type.value,
            intent_type=best_intent_type,
            confidence=best_score,
            entities=entities,
            suggested_tools=suggested_tools,
            sub_intent=sub_intent,
            reasoning=f"Matched patterns: {best_score:.2f} confidence"
        )
    
    def extract_entities(self, query: str) -> Dict[str, str]:
        """Extract Planning dimension entities from query."""
        entities = {}
        processed = self._preprocess_query(query)
        aliased_processed = self._replace_aliases(processed)
        
        for entity_type, pattern in self._compiled_entity_patterns.items():
            match = pattern.search(aliased_processed)
            if match:
                value = match.group(0)
                normalizer = self.ENTITY_PATTERNS[entity_type].get("normalize")
                if normalizer:
                    value = normalizer(value)
                entities[entity_type] = value
        
        return entities
    
    def _preprocess_query(self, query: str) -> str:
        """Preprocess query for better matching."""
        processed = query.lower()
        processed = re.sub(r'\s+', ' ', processed).strip()
        return processed
    
    def _replace_aliases(self, query: str) -> str:
        """Replace known aliases with canonical forms."""
        result = query.lower()
        for alias, canonical in self.ALIASES.items():
            result = re.sub(rf'\b{re.escape(alias)}\b', canonical, result, flags=re.IGNORECASE)
        return result
    
    def _score_intents(self, query: str, entities: Dict[str, str]) -> Dict[IntentType, float]:
        """Score each intent type for the query."""
        scores = {}
        for intent_type, config in self.INTENT_CONFIG.items():
            pattern_score = self._calculate_pattern_score(query, self._compiled_patterns[intent_type])
            keyword_score = self._calculate_keyword_score(query, config.get("keywords", []), config.get("negative_keywords", []))
            entity_score = self._calculate_entity_relevance(entities, intent_type)
            
            total_score = (pattern_score * 0.50 + keyword_score * 0.30 + entity_score * 0.20)
            scores[intent_type] = total_score
        return scores
    
    def _calculate_pattern_score(self, query: str, patterns: List[re.Pattern]) -> float:
        if not patterns: return 0.0
        matches = sum(1 for p in patterns if p.search(query))
        return min(1.0, (matches / len(patterns)) ** 0.5) if patterns else 0.0
    
    def _calculate_keyword_score(self, query: str, keywords: List[str], negative_keywords: List[str]) -> float:
        if not keywords: return 0.0
        positive_matches = sum(1 for kw in keywords if kw.lower() in query)
        positive_score = min(1.0, positive_matches / len(keywords))
        negative_matches = sum(1 for kw in negative_keywords if kw.lower() in query)
        negative_penalty = min(0.5, negative_matches * 0.15)
        return max(0.0, positive_score - negative_penalty)
    
    def _calculate_entity_relevance(self, entities: Dict[str, str], intent_type: IntentType) -> float:
        relevance_map = {
            IntentType.DATA_RETRIEVAL: ["account", "entity", "period", "year", "scenario"],
            IntentType.DIMENSION_EXPLORATION: ["entity", "account", "cost_center", "region"],
            IntentType.JOB_MANAGEMENT: ["job_id"],
            IntentType.VARIANCE_ANALYSIS: ["scenario", "period", "year", "account"],
            IntentType.DATA_MANAGEMENT: ["scenario", "period", "year"],
            IntentType.SUBSTITUTION_VARIABLES: [],
            IntentType.DOCUMENT_MANAGEMENT: [],
        }
        relevant_types = relevance_map.get(intent_type, [])
        if not relevant_types: return 0.0
        matches = sum(1 for et in relevant_types if et in entities)
        return matches / len(relevant_types)
    
    def _detect_sub_intent(self, query: str, intent_type: IntentType) -> Optional[str]:
        config = self.INTENT_CONFIG.get(intent_type, {})
        sub_intents = config.get("sub_intents", {})
        for sub_name, pattern in sub_intents.items():
            if re.search(pattern, query, re.IGNORECASE):
                return sub_name
        return None
    
    def _classify_with_llm(self, query: str, entities: Dict[str, str]) -> Intent:
        if not self._llm_reasoner:
            return Intent(
                name=IntentType.UNKNOWN.value,
                intent_type=IntentType.UNKNOWN,
                confidence=0.0,
                entities=entities,
                suggested_tools=["get_application_info"],
                reasoning="LLM not available"
            )
        return self._llm_reasoner.classify_intent(query, entities)
