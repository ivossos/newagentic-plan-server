"""Reinforcement Learning Service for tool selection and optimization using PostgreSQL."""

import hashlib
import json
from datetime import datetime
from typing import Optional

import numpy as np
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, create_engine, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker

from planning_agent.services.feedback_service import FeedbackService

Base = declarative_base()


class RLPolicy(Base):
    """RL Policy table for storing Q-values and action values."""

    __tablename__ = "rl_policy"

    id = Column(Integer, primary_key=True)
    tool_name = Column(String(255), nullable=False, index=True)
    context_hash = Column(String(64), nullable=False, index=True)
    action_value = Column(Float, default=0.0)  # Q-value or expected reward
    visit_count = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('tool_name', 'context_hash', name='uq_tool_context'),
    )


class RLEpisode(Base):
    """RL Episode table for tracking complete sessions."""

    __tablename__ = "rl_episodes"

    id = Column(Integer, primary_key=True)
    session_id = Column(String(255), nullable=False, index=True)
    episode_reward = Column(Float, default=0.0)
    tool_sequence = Column(JSON)  # List of tool names used in sequence
    outcome = Column(String(50))  # 'success', 'partial', 'failure'
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class RewardCalculator:
    """Calculate rewards from tool execution results."""

    @staticmethod
    def calculate_reward(
        execution_doc: dict,
        avg_execution_time: Optional[float] = None
    ) -> float:
        """Calculate reward for a tool execution.
        
        Reward Components:
        - Success: +10 if succeeded, -5 if failed
        - User Rating: (rating - 3) * 2 (normalized to -4 to +4)
        - Performance: -0.1 * (execution_time_ms / 1000) (penalize slow)
        - Efficiency Bonus: +2 if execution_time < avg * 0.8
        
        Returns:
            float: Total reward in range approximately -9 to +16
        """
        reward = 0.0
        
        # Success reward
        if execution_doc.get("success"):
            reward += 10.0
        else:
            reward -= 5.0
        
        # User rating reward (if available)
        user_rating = execution_doc.get("user_rating")
        if user_rating is not None:
            rating_reward = (user_rating - 3) * 2.0
            reward += rating_reward
        
        # Performance penalty (normalize execution time)
        execution_time_ms = execution_doc.get("execution_time_ms")
        if execution_time_ms:
            time_penalty = -0.1 * (execution_time_ms / 1000.0)
            reward += time_penalty
            
            # Efficiency bonus
            if avg_execution_time and execution_time_ms < avg_execution_time * 0.8:
                reward += 2.0
        
        return reward


class ToolSelector:
    """Intelligent tool selection based on RL policy and context."""

    def __init__(
        self,
        feedback_service: FeedbackService,
        exploration_rate: float = 0.1,
        min_samples: int = 5
    ):
        self.feedback_service = feedback_service
        self.exploration_rate = exploration_rate
        self.min_samples = min_samples
        self._tool_metadata_cache: Optional[dict] = None

    def create_context_hash(
        self,
        user_query: str = "",
        previous_tool: Optional[str] = None,
        session_length: int = 0
    ) -> str:
        """Create a hash representing the current state/context.
        
        Args:
            user_query: User's query or intent
            previous_tool: Previously executed tool name
            session_length: Number of tools executed in this session
            
        Returns:
            str: SHA256 hash of the context
        """
        # Extract keywords from query (simple approach)
        keywords = self._extract_keywords(user_query)
        
        context = {
            "keywords": sorted(keywords),
            "previous_tool": previous_tool or "",
            "session_length": session_length
        }
        
        context_str = json.dumps(context, sort_keys=True)
        return hashlib.sha256(context_str.encode()).hexdigest()

    def _extract_keywords(self, query: str) -> list[str]:
        """Extract relevant keywords from user query."""
        if not query:
            return []
        
        # Common Planning-related keywords
        planning_keywords = [
            "dimension", "member", "account", "entity", "period", "scenario",
            "version", "plan", "data", "retrieve", "export", "import",
            "rule", "job", "status", "hierarchy", "variable", "document",
            "snapshot", "costcenter", "region"
        ]
        
        query_lower = query.lower()
        found_keywords = [kw for kw in planning_keywords if kw in query_lower]
        
        # Also include first few words as keywords
        words = query_lower.split()[:5]
        found_keywords.extend(words)
        
        return list(set(found_keywords))  # Remove duplicates

    def get_tool_recommendations(
        self,
        context_hash: str,
        available_tools: list[str],
        rl_policy: Optional[dict] = None
    ) -> list[dict]:
        """Get ranked list of recommended tools with confidence scores."""
        recommendations = []
        
        # Get tool metrics from feedback service
        all_metrics = self.feedback_service.get_tool_metrics()
        metrics_dict = {m["tool_name"]: m for m in all_metrics}
        
        for tool_name in available_tools:
            confidence = 0.5  # Default confidence
            reason = "Baseline recommendation"
            
            # Get metrics for this tool
            tool_metrics = metrics_dict.get(tool_name, {})
            
            # Calculate confidence based on multiple factors
            factors = []
            
            # Factor 1: Success rate
            success_rate = tool_metrics.get("success_rate", 0.5)
            if success_rate > 0.8:
                confidence += 0.2
                factors.append("high success rate")
            elif success_rate < 0.5:
                confidence -= 0.2
                factors.append("low success rate")
            
            # Factor 2: User ratings
            avg_rating = tool_metrics.get("avg_user_rating")
            if avg_rating:
                if avg_rating >= 4.0:
                    confidence += 0.15
                    factors.append("high user rating")
                elif avg_rating < 3.0:
                    confidence -= 0.15
                    factors.append("low user rating")
            
            # Factor 3: Execution time (faster is better)
            avg_time = tool_metrics.get("avg_execution_time_ms", 0)
            if avg_time > 0 and avg_time < 1000:  # Less than 1 second
                confidence += 0.1
                factors.append("fast execution")
            
            # Factor 4: RL policy value (if available)
            if rl_policy:
                policy_key = f"{tool_name}:{context_hash}"
                action_value = rl_policy.get(policy_key, 0.0)
                if action_value > 0:
                    confidence += min(0.2, action_value / 10.0)  # Normalize
                    factors.append("RL policy favor")
            
            # Factor 5: Sample size (more samples = more reliable)
            total_calls = tool_metrics.get("total_calls", 0)
            if total_calls >= self.min_samples:
                confidence += 0.05
                factors.append("sufficient samples")
            
            # Clamp confidence to [0, 1]
            confidence = max(0.0, min(1.0, confidence))
            
            if factors:
                reason = ", ".join(factors)
            
            recommendations.append({
                "tool_name": tool_name,
                "confidence": round(confidence, 3),
                "reason": reason,
                "metrics": {
                    "success_rate": success_rate,
                    "avg_rating": avg_rating,
                    "total_calls": total_calls
                }
            })
        
        # Sort by confidence (descending)
        recommendations.sort(key=lambda x: x["confidence"], reverse=True)
        
        return recommendations


class RLService:
    """Main RL service coordinating all RL components using PostgreSQL."""

    def __init__(
        self,
        feedback_service: FeedbackService,
        db_url: str,
        exploration_rate: float = 0.1,
        learning_rate: float = 0.1,
        discount_factor: float = 0.9,
        min_samples: int = 5
    ):
        self.feedback_service = feedback_service
        self.exploration_rate = exploration_rate
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.min_samples = min_samples
        
        # Initialize PostgreSQL connection
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        
        # Initialize components
        self.reward_calculator = RewardCalculator()
        self.tool_selector = ToolSelector(
            feedback_service,
            exploration_rate=exploration_rate,
            min_samples=min_samples
        )
        
        # Cache for policy values (in-memory for performance)
        self._policy_cache: dict[str, float] = {}
        self._cache_updated = False

    def calculate_reward(self, execution_doc: dict) -> float:
        """Calculate reward for a tool execution."""
        # Get average execution time for this tool
        metrics = self.feedback_service.get_tool_metrics(execution_doc.get("tool_name"))
        avg_time = metrics[0].get("avg_execution_time_ms") if metrics else None
        
        return self.reward_calculator.calculate_reward(execution_doc, avg_time)

    def get_tool_recommendations(
        self,
        user_query: str = "",
        previous_tool: Optional[str] = None,
        session_length: int = 0,
        available_tools: Optional[list[str]] = None
    ) -> list[dict]:
        """Get tool recommendations for current context."""
        # Create context hash
        context_hash = self.tool_selector.create_context_hash(
            user_query, previous_tool, session_length
        )
        
        # Get available tools
        if available_tools is None:
            # Get all tools from feedback service metrics
            all_metrics = self.feedback_service.get_tool_metrics()
            available_tools = [m["tool_name"] for m in all_metrics]
        
        # Get RL policy
        rl_policy = self._get_policy_dict()
        
        return self.tool_selector.get_tool_recommendations(
            context_hash, available_tools, rl_policy
        )

    def get_max_q_value(self, context_hash: str, available_tools: Optional[list[str]] = None) -> float:
        """Get the maximum Q-value for a given context across all tools.

        Args:
            context_hash: The context/state hash
            available_tools: Optional list of tools to consider

        Returns:
            float: Maximum Q-value for this context (0.0 if no data)
        """
        policy_dict = self._get_policy_dict()

        max_q = 0.0
        for key, value in policy_dict.items():
            tool_name, ctx_hash = key.rsplit(":", 1)
            if ctx_hash == context_hash:
                if available_tools is None or tool_name in available_tools:
                    max_q = max(max_q, value)

        return max_q

    def update_policy(
        self,
        session_id: str,
        tool_name: str,
        context_hash: str,
        reward: float,
        next_context_hash: Optional[str] = None,
        available_tools: Optional[list[str]] = None,
        is_terminal: bool = False
    ):
        """Update RL policy using Q-learning update rule.

        Q(s,a) = Q(s,a) + α * (r + γ * max_a' Q(s',a') - Q(s,a))

        Args:
            session_id: Session identifier
            tool_name: The tool/action that was executed
            context_hash: The state hash before action
            reward: Immediate reward received
            next_context_hash: The state hash after action (for TD learning)
            available_tools: Tools available for max Q calculation
            is_terminal: Whether this is a terminal state (no future rewards)
        """
        with self.Session() as session:
            # Get or create policy entry
            policy = session.query(RLPolicy).filter_by(
                tool_name=tool_name,
                context_hash=context_hash
            ).first()

            if not policy:
                # Create new policy
                old_value = 0.0
                visit_count = 0
            else:
                old_value = policy.action_value or 0.0
                visit_count = policy.visit_count or 0

            # Calculate future value (TD target)
            if is_terminal or next_context_hash is None:
                # Terminal state or no next state - no future rewards
                future_value = 0.0
            else:
                # Get max Q-value for next state
                future_value = self.get_max_q_value(next_context_hash, available_tools)

            # Q-learning update: Q(s,a) = Q(s,a) + α * (r + γ * max Q(s',a') - Q(s,a))
            td_target = reward + self.discount_factor * future_value
            new_value = old_value + self.learning_rate * (td_target - old_value)
            visit_count += 1

            if policy:
                # Update existing policy
                policy.action_value = new_value
                policy.visit_count = visit_count
                policy.last_updated = datetime.utcnow()
            else:
                # Insert new policy
                policy = RLPolicy(
                    tool_name=tool_name,
                    context_hash=context_hash,
                    action_value=new_value,
                    visit_count=visit_count
                )
                session.add(policy)

            session.commit()

            # Update cache
            cache_key = f"{tool_name}:{context_hash}"
            self._policy_cache[cache_key] = new_value
            self._cache_updated = True

    def _get_policy_dict(self) -> dict[str, float]:
        """Get policy as dictionary for fast lookup."""
        if not self._cache_updated:
            # Load from database
            with self.Session() as session:
                for policy in session.query(RLPolicy).all():
                    key = f"{policy.tool_name}:{policy.context_hash}"
                    self._policy_cache[key] = policy.action_value or 0.0
            self._cache_updated = True
        
        return self._policy_cache

    def get_tool_confidence(
        self,
        tool_name: str,
        context_hash: str
    ) -> float:
        """Get confidence score for a tool in given context."""
        policy_dict = self._get_policy_dict()
        key = f"{tool_name}:{context_hash}"
        action_value = policy_dict.get(key, 0.0)
        
        # Normalize to [0, 1] range using sigmoid-like function
        confidence = 1.0 / (1.0 + np.exp(-action_value / 5.0))
        return float(confidence)

    def log_episode(
        self,
        session_id: str,
        tool_sequence: list[str],
        episode_reward: float,
        outcome: str = "success"
    ):
        """Log a complete episode (session) for sequence learning."""
        with self.Session() as session:
            episode = RLEpisode(
                session_id=session_id,
                episode_reward=episode_reward,
                tool_sequence=tool_sequence,
                outcome=outcome
            )
            session.add(episode)
            session.commit()

    def update_policy_with_feedback(
        self,
        execution_id: int,
        rating: int
    ) -> bool:
        """Update Q-value retroactively when user feedback arrives.
        
        This recalculates the reward with the actual user rating and
        updates the Q-value with the reward delta.
        
        Args:
            execution_id: The tool execution ID
            rating: User rating (1-5)
            
        Returns:
            bool: True if update was successful
        """
        # Get execution details
        execution = self.feedback_service.get_execution(execution_id)
        if not execution:
            return False
        
        # Need context_hash to update the right policy entry
        context_hash = execution.get("context_hash")
        if not context_hash:
            return False
        
        tool_name = execution.get("tool_name")
        success = execution.get("success")
        execution_time_ms = execution.get("execution_time_ms")
        
        # Calculate new reward with actual rating
        new_reward = self.reward_calculator.calculate_reward({
            "success": success,
            "user_rating": rating,
            "execution_time_ms": execution_time_ms,
            "tool_name": tool_name
        })
        
        # Calculate old reward (without rating)
        old_reward = self.reward_calculator.calculate_reward({
            "success": success,
            "user_rating": None,
            "execution_time_ms": execution_time_ms,
            "tool_name": tool_name
        })
        
        # Calculate reward delta
        reward_delta = new_reward - old_reward
        
        # Update Q-value: Q = Q + alpha * reward_delta
        with self.Session() as session:
            policy = session.query(RLPolicy).filter_by(
                tool_name=tool_name,
                context_hash=context_hash
            ).first()
            
            if policy:
                policy.action_value = (policy.action_value or 0.0) + self.learning_rate * reward_delta
                policy.last_updated = datetime.utcnow()
                session.commit()
                
                # Update cache
                cache_key = f"{tool_name}:{context_hash}"
                self._policy_cache[cache_key] = policy.action_value
                
                return True
        
        return False

    def get_successful_sequences(
        self,
        tool_name: Optional[str] = None,
        limit: int = 10
    ) -> list[dict]:
        """Get successful tool sequences for pattern learning."""
        try:
            with self.Session() as session:
                query = session.query(RLEpisode).filter_by(outcome="success")
                query = query.order_by(RLEpisode.episode_reward.desc()).limit(limit * 2 if tool_name else limit)
                
                episodes = query.all()
                
                # Filter by tool_name if specified
                if tool_name:
                    episodes = [
                        e for e in episodes
                        if e.tool_sequence and isinstance(e.tool_sequence, list) and tool_name in e.tool_sequence
                    ][:limit]
                
                return [
                    {
                        "session_id": e.session_id,
                        "tool_sequence": e.tool_sequence or [],
                        "episode_reward": e.episode_reward or 0.0,
                        "created_at": e.created_at.isoformat() if e.created_at else None
                    }
                    for e in episodes
                ]
        except Exception as e:
            # Log error but don't crash - return empty list
            import sys
            print(f"Warning: Failed to get successful sequences: {e}", file=sys.stderr)
            return []


# Global RL service instance
_rl_service: Optional[RLService] = None


def init_rl_service(
    feedback_service: FeedbackService,
    db_url: str,
    exploration_rate: float = 0.1,
    learning_rate: float = 0.1,
    discount_factor: float = 0.9,
    min_samples: int = 5
) -> RLService:
    """Initialize the global RL service."""
    global _rl_service
    _rl_service = RLService(
        feedback_service,
        db_url,
        exploration_rate=exploration_rate,
        learning_rate=learning_rate,
        discount_factor=discount_factor,
        min_samples=min_samples
    )
    return _rl_service


def get_rl_service() -> Optional[RLService]:
    """Get the global RL service instance."""
    return _rl_service
