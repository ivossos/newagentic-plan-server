"""Multi-step Planning for Planning operations.

Decomposes complex user queries into executable steps,
handles dependencies, and provides parallel execution strategies.
"""

from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import copy


class StepStatus(Enum):
    """Execution step status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ExecutionStep:
    """A single step in an execution plan."""
    id: int
    tool_name: str
    parameters: Dict[str, Any]
    depends_on: List[int] = field(default_factory=list)  # Step IDs this depends on
    description: str = ""
    status: StepStatus = StepStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    parallel_group: int = 0  # Steps in same group can run in parallel
    optional: bool = False  # If True, failure doesn't stop the plan
    retry_count: int = 0
    max_retries: int = 2
    
    def can_execute(self, completed_steps: Set[int]) -> bool:
        """Check if all dependencies are satisfied."""
        return all(dep_id in completed_steps for dep_id in self.depends_on)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "tool_name": self.tool_name,
            "parameters": self.parameters,
            "depends_on": self.depends_on,
            "description": self.description,
            "status": self.status.value,
            "parallel_group": self.parallel_group,
            "optional": self.optional,
        }


@dataclass
class ExecutionPlan:
    """A complete execution plan with multiple steps."""
    steps: List[ExecutionStep]
    name: str = "Unnamed Plan"
    description: str = ""
    estimated_duration_seconds: float = 0.0
    
    def get_ready_steps(self, completed_steps: Set[int]) -> List[ExecutionStep]:
        """Get steps that are ready to execute."""
        return [
            step for step in self.steps
            if step.status == StepStatus.PENDING and step.can_execute(completed_steps)
        ]
    
    def get_parallel_groups(self) -> Dict[int, List[ExecutionStep]]:
        """Group steps by parallel execution group."""
        groups = {}
        for step in self.steps:
            if step.parallel_group not in groups:
                groups[step.parallel_group] = []
            groups[step.parallel_group].append(step)
        return groups
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
            "estimated_duration_seconds": self.estimated_duration_seconds,
        }


class PlanningPlanner:
    """Plan multi-step tool executions for complex Planning queries."""
    
    # Pre-defined execution patterns for common Planning operations
    PATTERNS = {
        "revenue_analysis": {
            "name": "Revenue Analysis",
            "description": "Analyze revenue across Rooms, F&B and Other departments",
            "steps": [
                {
                    "tool": "smart_retrieve_revenue",
                    "params_template": {},
                    "desc": "Retrieve comprehensive revenue breakdown",
                    "parallel_group": 0
                },
                {
                    "tool": "smart_retrieve_monthly",
                    "params_template": {"account": "400000"},
                    "desc": "Retrieve monthly revenue trend",
                    "parallel_group": 1
                },
            ],
            "triggers": ["revenue", "rooms", "f&b", "sales", "income statement"],
            "estimated_duration": 8.0,
            "priority": 10
        },
        "variance_analysis": {
            "name": "Variance Analysis",
            "description": "Compare actual results against forecast or prior year",
            "steps": [
                {
                    "tool": "smart_retrieve_variance",
                    "params_template": {},
                    "desc": "Execute variance analysis",
                    "parallel_group": 0
                },
            ],
            "triggers": ["variance", "compare", "actual vs forecast", "actual vs budget", "versus", "vs"],
            "estimated_duration": 6.0,
            "priority": 8
        },
        "copy_plan": {
            "name": "Plan Data Copy",
            "description": "Copy data between scenarios (e.g., Forecast to Budget)",
            "steps": [
                {
                    "tool": "copy_data",
                    "params_template": {},
                    "desc": "Copy data across scenarios/years",
                    "parallel_group": 0
                },
            ],
            "triggers": ["copy data", "copy from", "duplicate plan"],
            "estimated_duration": 15.0,
            "priority": 7
        },
        "dimension_check": {
            "name": "Dimension Check",
            "description": "Explore dimensions and members",
            "steps": [
                {
                    "tool": "get_dimensions",
                    "params_template": {},
                    "desc": "List all dimensions",
                    "parallel_group": 0
                },
                {
                    "tool": "get_members",
                    "params_template": {"dimension_name": "Entity"},
                    "desc": "List entity members",
                    "parallel_group": 1,
                    "optional": True
                },
            ],
            "triggers": ["list entities", "show dimensions", "what are the members", "dimension list"],
            "estimated_duration": 5.0,
            "priority": 6
        },
    }
    
    # Tool categories for dynamic planning
    TOOL_CATEGORIES = {
        "retrieval": ["smart_retrieve", "smart_retrieve_revenue", "smart_retrieve_monthly", "smart_retrieve_variance", "export_data_slice"],
        "dimension": ["get_dimensions", "get_members", "get_member"],
        "job": ["list_jobs", "get_job_status", "execute_job"],
        "data": ["copy_data", "clear_data"],
        "vars": ["get_substitution_variables", "set_substitution_variable"],
        "docs": ["get_documents", "get_snapshots"],
        "info": ["get_application_info", "get_rest_api_version"],
    }
    
    # Tool estimated durations (seconds)
    TOOL_DURATIONS = {
        "smart_retrieve": 3.0,
        "smart_retrieve_revenue": 4.0,
        "smart_retrieve_monthly": 5.0,
        "smart_retrieve_variance": 4.0,
        "export_data_slice": 6.0,
        "get_dimensions": 2.0,
        "get_members": 3.0,
        "list_jobs": 2.0,
        "execute_job": 20.0,
        "copy_data": 15.0,
        "clear_data": 10.0,
    }
    
    def __init__(self):
        """Initialize planner."""
        self._step_counter = 0
    
    def create_plan(
        self,
        intent: str,
        entities: Dict[str, str],
        available_tools: List[str],
        sub_intent: Optional[str] = None,
        suggested_tools: Optional[List[str]] = None,
        user_query: Optional[str] = None
    ) -> ExecutionPlan:
        """Create execution plan for intent."""
        self._step_counter = 0
        pattern = self._match_pattern(intent, entities, sub_intent, user_query)
        if pattern:
            return self._build_from_pattern(pattern, entities, available_tools)
        return self._dynamic_plan(intent, entities, available_tools, suggested_tools)
    
    def _match_pattern(self, intent: str, entities: Dict[str, str], sub_intent: Optional[str] = None, user_query: Optional[str] = None) -> Optional[Dict]:
        query_text = user_query.lower() if user_query else ""
        # Ensure all entity values are strings to avoid TypeError in join
        entity_values = [str(v) for v in entities.values()]
        combined_context = f"{query_text} {intent} {sub_intent or ''} {' '.join(entity_values)}".lower()
        best_match = None
        best_score = 0
        for pattern_name, pattern in self.PATTERNS.items():
            triggers = pattern.get("triggers", [])
            priority = pattern.get("priority", 1)
            matches = sum(1 for t in triggers if t.lower() in combined_context)
            if matches > 0:
                score = matches + (priority * 0.5)
                if score > best_score:
                    best_score = score
                    best_match = pattern
        return best_match if best_score >= 1 else None
    
    def _build_from_pattern(self, pattern: Dict, entities: Dict[str, str], available_tools: List[str]) -> ExecutionPlan:
        steps = []
        for step_template in pattern["steps"]:
            tool_name = step_template["tool"]
            if tool_name not in available_tools: continue
            template_params = copy.deepcopy(step_template.get("params_template", {}))
            entity_params = self._filter_params_for_tool(tool_name, entities)
            params = {**entity_params, **template_params}
            step = ExecutionStep(
                id=self._next_step_id(),
                tool_name=tool_name,
                parameters=params,
                depends_on=self._calculate_dependencies(steps, step_template),
                description=step_template.get("desc", f"Execute {tool_name}"),
                parallel_group=step_template.get("parallel_group", 0),
                optional=step_template.get("optional", False),
            )
            steps.append(step)
        if not steps: steps = self._create_fallback_steps(entities, available_tools)
        return ExecutionPlan(steps=steps, name=pattern.get("name", "Execution Plan"), description=pattern.get("description", ""), estimated_duration_seconds=pattern.get("estimated_duration", 10.0))
    
    def _dynamic_plan(self, intent: str, entities: Dict[str, str], available_tools: List[str], suggested_tools: Optional[List[str]] = None) -> ExecutionPlan:
        steps = []
        tools_to_use = suggested_tools or self._infer_tools_from_intent(intent, available_tools)
        tools_to_use = [t for t in tools_to_use if t in available_tools]
        for i, tool_name in enumerate(tools_to_use[:3]):
            params = self._filter_params_for_tool(tool_name, entities)
            step = ExecutionStep(id=self._next_step_id(), tool_name=tool_name, parameters=params, depends_on=[steps[-1].id] if steps else [], description=f"Execute {tool_name}", parallel_group=i)
            steps.append(step)
        if not steps: steps = self._create_fallback_steps(entities, available_tools)
        estimated_duration = sum(self.TOOL_DURATIONS.get(s.tool_name, 5.0) for s in steps)
        return ExecutionPlan(steps=steps, name="Dynamic Execution Plan", description=f"Generated plan for intent: {intent}", estimated_duration_seconds=estimated_duration)
    
    def _infer_tools_from_intent(self, intent: str, available_tools: List[str]) -> List[str]:
        intent_tool_map = {
            "data_retrieval": ["smart_retrieve"],
            "dimension_exploration": ["get_dimensions", "get_members"],
            "job_management": ["list_jobs"],
            "reporting": ["get_documents"],
            "variance_analysis": ["smart_retrieve_variance"],
            "data_management": ["copy_data"],
            "substitution_variables": ["get_substitution_variables"],
        }
        return intent_tool_map.get(intent, ["get_application_info"])
    
    def _filter_params_for_tool(self, tool_name: str, entities: Dict[str, str]) -> Dict[str, Any]:
        tool_params = {
            "smart_retrieve": ["account", "entity", "period", "years", "scenario", "version", "cost_center", "region", "currency"],
            "smart_retrieve_revenue": ["entity", "period", "years", "scenario", "cost_center"],
            "smart_retrieve_monthly": ["account", "entity", "years", "scenario", "cost_center"],
            "smart_retrieve_variance": ["account", "entity", "period", "years", "prior_year", "cost_center"],
            "export_data_slice": ["plan_type", "grid_definition"],
            "get_members": ["dimension_name"],
            "get_member": ["dimension_name", "member_name", "expansion"],
            "execute_job": ["job_type", "job_name", "parameters"],
            "copy_data": ["from_scenario", "from_year", "from_period", "to_scenario", "to_year", "to_period"],
            "clear_data": ["scenario", "year", "period"],
            "get_substitution_variables": [],
            "set_substitution_variable": ["variable_name", "value", "plan_type"],
            "get_documents": [],
            "get_snapshots": [],
            "list_jobs": [],
            "get_job_status": ["job_id"],
            "get_dimensions": [],
        }
        valid_params = tool_params.get(tool_name, [])
        entity_to_param = {
            "period": "period",
            "year": "years",
            "scenario": "scenario",
            "account": "account",
            "entity": "entity",
            "cost_center": "cost_center",
            "region": "region",
            "version": "version",
            "currency": "currency",
            "job_id": "job_id",
        }
        filtered = {}
        for entity_type, value in entities.items():
            param_name = entity_to_param.get(entity_type, entity_type)
            if param_name in valid_params: filtered[param_name] = value
        
        # Special handling for years/year
        if "year" in entities:
            if "years" in valid_params: filtered["years"] = entities["year"]
            if "year" in valid_params: filtered["year"] = entities["year"]
            if "from_year" in valid_params: filtered["from_year"] = entities["year"]
            if "to_year" in valid_params: filtered["to_year"] = entities["year"]
        
        # Defaults for retrieval
        if tool_name.startswith("smart_retrieve") and "account" in valid_params and "account" not in filtered:
            filtered["account"] = "400000" if "revenue" in tool_name else "Net Income"
        
        return filtered
    
    def _calculate_dependencies(self, existing_steps: List[ExecutionStep], step_template: Dict) -> List[int]:
        parallel_group = step_template.get("parallel_group", 0)
        if parallel_group == 0: return []
        prev_group = parallel_group - 1
        return [s.id for s in existing_steps if s.parallel_group == prev_group]
    
    def _create_fallback_steps(self, entities: Dict[str, str], available_tools: List[str]) -> List[ExecutionStep]:
        default_tool = "get_application_info"
        if default_tool not in available_tools:
            default_tool = available_tools[0] if available_tools else "get_application_info"
        return [ExecutionStep(id=self._next_step_id(), tool_name=default_tool, parameters={}, description=f"Execute {default_tool}")]
    
    def _next_step_id(self) -> int:
        self._step_counter += 1
        return self._step_counter
    
    def get_parallel_groups(self, plan: ExecutionPlan) -> Dict[int, List[ExecutionStep]]:
        return plan.get_parallel_groups()
