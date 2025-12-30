"""Context Memory for Planning conversations.

Manages persistent and session-based context including:
- Point of View (POV) state
- Entity focus tracking
- Query history
- Result caching for context enrichment
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import deque
import hashlib
import json
import threading

from sqlalchemy import Column, Integer, String, DateTime, JSON, Float, Text, Index, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


class ConversationContext(Base):
    """Persistent conversation context storage."""
    __tablename__ = "conversation_context"
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String(255), nullable=False, index=True)
    context_type = Column(String(50), nullable=False)  # "pov", "entity_focus", "query_history"
    context_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime)
    
    __table_args__ = (
        Index('ix_context_session_type', 'session_id', 'context_type'),
    )


class QueryHistory(Base):
    """Track query history for learning patterns."""
    __tablename__ = "query_history"
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String(255), nullable=False, index=True)
    query_text = Column(Text)
    intent = Column(String(100))
    entities = Column(JSON)
    tools_used = Column(JSON)
    success = Column(Integer)  # 1 = success, 0 = failure
    execution_time_ms = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class ResultCache(Base):
    """Cache recent results for context enrichment."""
    __tablename__ = "result_cache"
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String(255), nullable=False, index=True)
    cache_key = Column(String(255), nullable=False, index=True)  # Hash of tool + params
    tool_name = Column(String(100))
    parameters = Column(JSON)
    result_summary = Column(JSON)  # Summarized result for context
    full_result = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    
    __table_args__ = (
        Index('ix_cache_session_key', 'session_id', 'cache_key'),
    )


@dataclass
class POVState:
    """Point of View state for Planning queries (PlanApp)."""
    years: str = "FY25"
    period: str = "YearTotal"
    scenario: str = "Actual"
    version: str = "Final"
    currency: str = "USD"
    entity: str = "E501"
    cost_center: str = "CC9999"
    future1: str = "No Future1"
    region: str = "R131"
    account: Optional[str] = None
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary."""
        return {
            "years": self.years,
            "period": self.period,
            "scenario": self.scenario,
            "version": self.version,
            "currency": self.currency,
            "entity": self.entity,
            "cost_center": self.cost_center,
            "future1": self.future1,
            "region": self.region,
            "account": self.account,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> 'POVState':
        """Create from dictionary."""
        return cls(
            years=data.get("years", "FY25"),
            period=data.get("period", "YearTotal"),
            scenario=data.get("scenario", "Actual"),
            version=data.get("version", "Final"),
            currency=data.get("currency", "USD"),
            entity=data.get("entity", "E501"),
            cost_center=data.get("cost_center", "CC9999"),
            future1=data.get("future1", "No Future1"),
            region=data.get("region", "R131"),
            account=data.get("account"),
        )
    
    def update(self, **kwargs) -> 'POVState':
        """Create updated copy with new values."""
        data = self.to_dict()
        data.update(kwargs)
        return POVState.from_dict(data)


@dataclass
class ConversationMemory:
    """In-memory conversation state."""
    pov: POVState = field(default_factory=POVState)
    recent_queries: deque = field(default_factory=lambda: deque(maxlen=10))
    recent_results: deque = field(default_factory=lambda: deque(maxlen=5))
    entity_focus: Optional[str] = None
    account_focus: Optional[str] = None
    last_tool_used: Optional[str] = None
    last_activity: datetime = field(default_factory=datetime.utcnow)
    
    def add_query(self, query: str, intent: str, entities: Dict[str, str]):
        """Add a query to history."""
        self.recent_queries.append({
            "query": query,
            "intent": intent,
            "entities": entities,
            "timestamp": datetime.utcnow().isoformat()
        })
        self.last_activity = datetime.utcnow()
    
    def add_result(self, tool_name: str, params: Dict, result_summary: Dict):
        """Add a result to history."""
        self.recent_results.append({
            "tool_name": tool_name,
            "params": params,
            "summary": result_summary,
            "timestamp": datetime.utcnow().isoformat()
        })
        self.last_tool_used = tool_name
        self.last_activity = datetime.utcnow()


class ContextMemory:
    """Manage conversation context for intelligent Planning operations."""
    
    # Default TTL for different context types (seconds)
    TTL_CONFIG = {
        "pov": 86400,           # 24 hours
        "entity_focus": 3600,   # 1 hour
        "query_history": 604800, # 7 days
        "result_cache": 1800,    # 30 minutes
    }
    
    def __init__(
        self,
        db_url: str,
        default_ttl: int = 3600,
        enable_persistence: bool = True
    ):
        """Initialize context memory."""
        self.db_url = db_url
        self.default_ttl = default_ttl
        self.enable_persistence = enable_persistence
        self._sessions: Dict[str, ConversationMemory] = {}
        self._lock = threading.RLock()
        
        if enable_persistence:
            self.engine = create_engine(db_url)
            Base.metadata.create_all(self.engine)
            self.Session = sessionmaker(bind=self.engine)
        else:
            self.Session = None
    
    def get_or_create_session(self, session_id: str) -> ConversationMemory:
        with self._lock:
            if session_id not in self._sessions:
                pov = self._load_pov(session_id)
                memory = ConversationMemory(pov=pov)
                self._sessions[session_id] = memory
            return self._sessions[session_id]
    
    def set_pov(self, session_id: str, **kwargs):
        memory = self.get_or_create_session(session_id)
        memory.pov = memory.pov.update(**kwargs)
        self._save_context(session_id, "pov", memory.pov.to_dict())
    
    def get_pov(self, session_id: str) -> POVState:
        return self.get_or_create_session(session_id).pov
    
    def update_from_entities(self, session_id: str, entities: Dict[str, str]):
        entity_to_pov = {
            "period": "period",
            "year": "years",
            "years": "years",
            "scenario": "scenario",
            "version": "version",
            "currency": "currency",
            "entity": "entity",
            "cost_center": "cost_center",
            "region": "region",
            "account": "account",
        }
        pov_updates = {entity_to_pov[k]: v for k, v in entities.items() if k in entity_to_pov}
        if pov_updates: self.set_pov(session_id, **pov_updates)
    
    def update_from_result(self, session_id: str, tool_name: str, result: Dict[str, Any]):
        memory = self.get_or_create_session(session_id)
        data = result.get("data", {})
        pov_updates = {}
        if isinstance(data, dict):
            for key in ["entity", "account", "period", "years", "scenario", "version", "cost_center", "region"]:
                if key in data: pov_updates[key] = data[key]
            if "entity" in data: memory.entity_focus = data["entity"]
            if "account" in data: memory.account_focus = data["account"]
        
        if pov_updates: self.set_pov(session_id, **pov_updates)
        params = result.get("parameters", {})
        summary = self._summarize_result(result)
        memory.add_result(tool_name, params, summary)
        cache_key = self._create_cache_key(tool_name, params)
        self._cache_result(session_id, cache_key, tool_name, params, summary, result)
    
    def get_suggested_params(self, session_id: str, tool_name: str) -> Dict[str, Any]:
        pov = self.get_pov(session_id)
        pov_dict = pov.to_dict()
        tool_params_map = {
            "smart_retrieve": ["account", "entity", "period", "years", "scenario", "version", "cost_center", "region", "currency"],
            "smart_retrieve_revenue": ["entity", "period", "years", "scenario", "cost_center"],
            "smart_retrieve_monthly": ["account", "entity", "years", "scenario", "cost_center"],
            "smart_retrieve_variance": ["account", "entity", "period", "years", "cost_center"],
        }
        relevant_params = tool_params_map.get(tool_name, [])
        return {p: pov_dict[p] for p in relevant_params if p in pov_dict and pov_dict[p]}
    
    def get_recent_context(self, session_id: str) -> Dict[str, Any]:
        memory = self.get_or_create_session(session_id)
        return {
            "current_pov": memory.pov.to_dict(),
            "entity_focus": memory.entity_focus,
            "account_focus": memory.account_focus,
            "last_tool_used": memory.last_tool_used,
            "recent_queries": list(memory.recent_queries)[-3:],
            "recent_results": list(memory.recent_results)[-2:],
        }

    def _load_pov(self, session_id: str) -> POVState:
        if not self.enable_persistence or not self.Session: return POVState()
        try:
            with self.Session() as session:
                ctx = session.query(ConversationContext).filter_by(session_id=session_id, context_type="pov").filter(ConversationContext.expires_at > datetime.utcnow()).first()
                if ctx and ctx.context_data: return POVState.from_dict(ctx.context_data)
        except: pass
        return POVState()

    def _save_context(self, session_id: str, context_type: str, data: Dict):
        if not self.enable_persistence or not self.Session: return
        ttl = self.TTL_CONFIG.get(context_type, self.default_ttl)
        expires_at = datetime.utcnow() + timedelta(seconds=ttl)
        try:
            with self.Session() as session:
                ctx = session.query(ConversationContext).filter_by(session_id=session_id, context_type=context_type).first()
                if ctx:
                    ctx.context_data = data
                    ctx.updated_at = datetime.utcnow()
                    ctx.expires_at = expires_at
                else:
                    ctx = ConversationContext(session_id=session_id, context_type=context_type, context_data=data, expires_at=expires_at)
                    session.add(ctx)
                session.commit()
        except: pass

    def _cache_result(self, session_id: str, cache_key: str, tool_name: str, params: Dict, summary: Dict, full_result: Dict):
        if not self.enable_persistence or not self.Session: return
        ttl = self.TTL_CONFIG.get("result_cache", 1800)
        expires_at = datetime.utcnow() + timedelta(seconds=ttl)
        try:
            with self.Session() as session:
                session.query(ResultCache).filter_by(session_id=session_id, cache_key=cache_key).delete()
                cache = ResultCache(session_id=session_id, cache_key=cache_key, tool_name=tool_name, parameters=params, result_summary=summary, full_result=full_result, expires_at=expires_at)
                session.add(cache)
                session.commit()
        except: pass

    def _create_cache_key(self, tool_name: str, params: Dict) -> str:
        content = json.dumps({"tool": tool_name, "params": params}, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def _summarize_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        summary = {"status": result.get("status"), "has_data": "data" in result}
        data = result.get("data", {})
        if isinstance(data, dict):
            for key in ["entity", "account", "period", "years", "scenario", "version"]:
                if key in data: summary[key] = data[key]
        return summary
