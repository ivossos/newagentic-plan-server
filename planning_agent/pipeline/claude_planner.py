"""Claude-based planner using Claude Agent SDK.

Wraps the ClaudeAdapter to provide a Planner interface for the
agentic pipeline.
"""

import logging
from typing import Dict, List, Optional

from planning_agent.pipeline.planner import Planner
from planning_agent.pipeline.types import Plan
from planning_agent.pipeline.claude_adapter import ClaudeAdapter

logger = logging.getLogger(__name__)


class ClaudePlanner(Planner):
    """Planner implementation using Claude Agent SDK for function calling.

    Uses Anthropic's Claude model to analyze natural language queries
    and generate execution plans by selecting appropriate tools.
    """

    def __init__(self, adapter: ClaudeAdapter):
        """Initialize the Claude planner.

        Args:
            adapter: ClaudeAdapter instance for Claude API communication.
        """
        self.adapter = adapter

    @property
    def is_available(self) -> bool:
        """Check if the planner is available for use."""
        return self.adapter.is_available

    async def plan(self, query: str, tool_catalog: List[Dict]) -> Plan:
        """Generate an execution plan for the given query.

        Args:
            query: The user's natural language query.
            tool_catalog: List of available tool definitions (MCP format).

        Returns:
            Plan object containing steps to execute.
        """
        if not self.is_available:
            logger.warning("ClaudePlanner not available - returning empty plan")
            return Plan(
                query=query,
                steps=[],
                notes="Claude planner unavailable"
            )

        try:
            plan = await self.adapter.plan(query, tool_catalog)
            logger.info(f"Generated plan with {len(plan.steps)} steps")
            return plan
        except Exception as e:
            logger.error(f"Planning error: {e}")
            return Plan(
                query=query,
                steps=[],
                notes=f"planning_error: {str(e)[:100]}"
            )
