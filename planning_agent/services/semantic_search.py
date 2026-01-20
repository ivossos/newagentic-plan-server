"""Semantic Search Service - Natural language member resolution using embeddings."""

import csv
import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np
from sqlalchemy import Column, Integer, String, DateTime, LargeBinary, create_engine, Index
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


class MemberEmbedding(Base):
    """Store embeddings for dimension members."""

    __tablename__ = "member_embeddings"

    id = Column(Integer, primary_key=True)
    dimension = Column(String(100), index=True, nullable=False)
    member_name = Column(String(255), nullable=False)
    alias = Column(String(255), nullable=True)
    parent = Column(String(255), nullable=True)
    embedding = Column(LargeBinary, nullable=False)  # Stored as numpy bytes
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_dim_member", "dimension", "member_name"),
    )


class LocalEmbedder:
    """Local embedding generator with optional sentence-transformers or hash-based fallback."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = None
        self.model_name = model_name
        self.embedding_dim = 384  # Default for MiniLM

        # Try to load sentence-transformers
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(model_name)
            self.embedding_dim = self.model.get_sentence_embedding_dimension()
        except ImportError:
            # Fallback to hash-based embeddings
            self.embedding_dim = 128

    def embed(self, text: str) -> np.ndarray:
        """Generate embedding for text."""
        if self.model:
            return self.model.encode(text, convert_to_numpy=True)
        else:
            return self._hash_embed(text)

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        """Generate embeddings for batch of texts."""
        if self.model:
            return self.model.encode(texts, convert_to_numpy=True)
        else:
            return np.array([self._hash_embed(t) for t in texts])

    def _hash_embed(self, text: str) -> np.ndarray:
        """Fallback hash-based embedding when sentence-transformers unavailable."""
        # Create deterministic pseudo-embedding from text hash
        text_lower = text.lower().strip()

        # Generate multiple hash values for dimensionality
        embeddings = []
        for i in range(self.embedding_dim):
            h = hashlib.md5(f"{text_lower}_{i}".encode()).hexdigest()
            # Convert hex to float in [-1, 1] range
            val = (int(h[:8], 16) / (2**32)) * 2 - 1
            embeddings.append(val)

        result = np.array(embeddings, dtype=np.float32)
        # Normalize
        norm = np.linalg.norm(result)
        if norm > 0:
            result = result / norm
        return result


# Planning-specific synonym expansions
PLANNING_SYNONYMS = {
    "revenue": ["revenue", "sales", "income", "receita", "vendas", "4000", "400000", "total revenue"],
    "expense": ["expense", "cost", "despesa", "custo", "5000", "500000", "6000", "operating expense"],
    "budget": ["budget", "orcamento", "plan", "planejado", "planned"],
    "forecast": ["forecast", "previsao", "projected", "projection"],
    "actual": ["actual", "realizado", "current", "actuals"],
    "variance": ["variance", "variacao", "delta", "difference", "var"],
    "net income": ["net income", "lucro liquido", "profit", "bottom line", "resultado"],
    "gross profit": ["gross profit", "lucro bruto", "margem bruta", "gross margin"],
    "rooms": ["rooms", "quartos", "room revenue", "410000", "lodging"],
    "food": ["food", "f&b", "food and beverage", "420000", "restaurant", "alimentos"],
    "chicago": ["chicago", "chi", "e501", "l7 chicago"],
    "miami": ["miami", "mia", "e502", "l7 miami"],
    "assets": ["assets", "ativos", "100000", "balance sheet assets"],
    "liabilities": ["liabilities", "passivos", "200000", "debt"],
    "equity": ["equity", "patrimonio", "300000", "stockholders equity"],
    "cash": ["cash", "caixa", "111000", "cash and cash equivalent"],
    "receivables": ["receivables", "contas a receber", "112000", "ar"],
    "payables": ["payables", "contas a pagar", "accounts payable", "ap"],
}


class SemanticSearchService:
    """Service for semantic search of dimension members."""

    def __init__(self, db_url: str):
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.embedder = LocalEmbedder()
        self._embedding_cache: dict[str, np.ndarray] = {}

    def index_member(
        self,
        dimension: str,
        member_name: str,
        alias: Optional[str] = None,
        parent: Optional[str] = None
    ) -> int:
        """Index a single dimension member."""
        # Create text for embedding (combine name, alias, and parent for context)
        text_parts = [member_name]
        if alias and alias != member_name:
            text_parts.append(alias)
        if parent:
            text_parts.append(f"parent:{parent}")

        text = " ".join(text_parts)
        embedding = self.embedder.embed(text)

        with self.Session() as session:
            # Check if exists
            existing = session.query(MemberEmbedding).filter(
                MemberEmbedding.dimension == dimension,
                MemberEmbedding.member_name == member_name
            ).first()

            if existing:
                existing.alias = alias
                existing.parent = parent
                existing.embedding = embedding.tobytes()
                existing.created_at = datetime.utcnow()
            else:
                member = MemberEmbedding(
                    dimension=dimension,
                    member_name=member_name,
                    alias=alias,
                    parent=parent,
                    embedding=embedding.tobytes()
                )
                session.add(member)

            session.commit()
            return existing.id if existing else member.id

    def index_members_batch(
        self,
        dimension: str,
        members: list[dict[str, Any]]
    ) -> int:
        """Index multiple members efficiently.

        Args:
            dimension: Dimension name
            members: List of dicts with 'name', optional 'alias', 'parent' keys

        Returns:
            Number of members indexed
        """
        if not members:
            return 0

        # Prepare texts for batch embedding
        texts = []
        for m in members:
            text_parts = [m["name"]]
            if m.get("alias") and m["alias"] != m["name"]:
                text_parts.append(m["alias"])
            if m.get("parent"):
                text_parts.append(f"parent:{m['parent']}")
            texts.append(" ".join(text_parts))

        embeddings = self.embedder.embed_batch(texts)

        with self.Session() as session:
            # Delete existing members for this dimension
            session.query(MemberEmbedding).filter(
                MemberEmbedding.dimension == dimension
            ).delete()

            # Add new members
            for i, m in enumerate(members):
                member = MemberEmbedding(
                    dimension=dimension,
                    member_name=m["name"],
                    alias=m.get("alias"),
                    parent=m.get("parent"),
                    embedding=embeddings[i].tobytes()
                )
                session.add(member)

            session.commit()

        return len(members)

    def search(
        self,
        query: str,
        dimension: Optional[str] = None,
        top_k: int = 10,
        threshold: float = 0.3
    ) -> list[dict[str, Any]]:
        """Search for members matching a natural language query.

        Args:
            query: Natural language query
            dimension: Optional dimension to filter by
            top_k: Maximum number of results
            threshold: Minimum similarity score (0-1)

        Returns:
            List of matching members with scores
        """
        # Expand query with synonyms
        expanded_query = self._expand_query(query)
        query_embedding = self.embedder.embed(expanded_query)

        with self.Session() as session:
            db_query = session.query(MemberEmbedding)
            if dimension:
                db_query = db_query.filter(MemberEmbedding.dimension == dimension)

            members = db_query.all()

            results = []
            for member in members:
                member_embedding = np.frombuffer(member.embedding, dtype=np.float32)

                # Cosine similarity
                similarity = np.dot(query_embedding, member_embedding) / (
                    np.linalg.norm(query_embedding) * np.linalg.norm(member_embedding) + 1e-8
                )

                if similarity >= threshold:
                    results.append({
                        "dimension": member.dimension,
                        "member_name": member.member_name,
                        "alias": member.alias,
                        "parent": member.parent,
                        "score": float(similarity)
                    })

            # Sort by score descending
            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:top_k]

    def search_by_dimension(
        self,
        query: str,
        dimension: str,
        top_k: int = 5
    ) -> list[dict[str, Any]]:
        """Search within a specific dimension."""
        return self.search(query, dimension=dimension, top_k=top_k)

    def resolve_member(
        self,
        fuzzy_input: str,
        dimension: Optional[str] = None,
        confidence_threshold: float = 0.5
    ) -> Optional[dict[str, Any]]:
        """Resolve fuzzy input to exact member name.

        Args:
            fuzzy_input: User's approximate member name
            dimension: Optional dimension to constrain search
            confidence_threshold: Minimum score to consider a match

        Returns:
            Best matching member or None if no confident match
        """
        # First try exact match
        with self.Session() as session:
            query = session.query(MemberEmbedding)
            if dimension:
                query = query.filter(MemberEmbedding.dimension == dimension)

            # Try exact match on name or alias
            exact = query.filter(
                (MemberEmbedding.member_name == fuzzy_input) |
                (MemberEmbedding.alias == fuzzy_input)
            ).first()

            if exact:
                return {
                    "dimension": exact.dimension,
                    "member_name": exact.member_name,
                    "alias": exact.alias,
                    "score": 1.0,
                    "match_type": "exact"
                }

        # Try semantic search
        results = self.search(fuzzy_input, dimension=dimension, top_k=1, threshold=confidence_threshold)
        if results:
            results[0]["match_type"] = "semantic"
            return results[0]

        return None

    def _expand_query(self, query: str) -> str:
        """Expand query with Planning-specific synonyms."""
        query_lower = query.lower()
        expanded_parts = [query]

        for key, synonyms in PLANNING_SYNONYMS.items():
            for syn in synonyms:
                if syn in query_lower:
                    # Add related terms
                    for related in synonyms:
                        if related not in query_lower and related not in expanded_parts:
                            expanded_parts.append(related)
                    break

        return " ".join(expanded_parts[:5])  # Limit expansion

    def get_indexed_dimensions(self) -> list[str]:
        """Get list of dimensions that have been indexed."""
        with self.Session() as session:
            results = session.query(MemberEmbedding.dimension).distinct().all()
            return [r[0] for r in results]

    def get_index_stats(self) -> dict[str, Any]:
        """Get statistics about the semantic index."""
        with self.Session() as session:
            from sqlalchemy import func

            total = session.query(func.count(MemberEmbedding.id)).scalar() or 0

            by_dimension = session.query(
                MemberEmbedding.dimension,
                func.count(MemberEmbedding.id)
            ).group_by(MemberEmbedding.dimension).all()

            return {
                "total_members": total,
                "dimensions": {dim: count for dim, count in by_dimension},
                "embedding_model": self.embedder.model_name if self.embedder.model else "hash-based",
                "embedding_dim": self.embedder.embedding_dim
            }


# Global state
_semantic_search_service: Optional[SemanticSearchService] = None


def init_semantic_search(db_url: str) -> Optional[SemanticSearchService]:
    """Initialize the global semantic search service."""
    global _semantic_search_service
    try:
        _semantic_search_service = SemanticSearchService(db_url)
        return _semantic_search_service
    except Exception as e:
        import sys
        print(f"Warning: Could not initialize semantic search service: {e}", file=sys.stderr)
        return None


def get_semantic_search_service() -> Optional[SemanticSearchService]:
    """Get the global semantic search service instance."""
    return _semantic_search_service


def index_from_csvs(
    service: Optional[SemanticSearchService] = None,
    data_dir: Optional[str] = None
) -> dict[str, int]:
    """Index dimension members from CSV files in the data directory.

    Expected CSV format: First column is member name, second is parent, third is alias.
    Files should be named: ExportedMetadata_<DimensionName>.csv

    Args:
        service: Semantic search service (uses global if not provided)
        data_dir: Directory containing CSVs (defaults to ./data)

    Returns:
        Dict mapping dimension name to count of indexed members
    """
    svc = service or _semantic_search_service
    if not svc:
        return {}

    if data_dir is None:
        # Default to data directory relative to project root
        data_dir = Path(__file__).parent.parent.parent / "data"
    else:
        data_dir = Path(data_dir)

    if not data_dir.exists():
        return {}

    results = {}

    # Dimension mappings from CSV file names
    dimension_files = {
        "Account": "ExportedMetadata_Account.csv",
        "Entity": "ExportedMetadata_Entity.csv",
        "CostCenter": "ExportedMetadata_CostCenter.csv",
        "Region": "ExportedMetadata_Region.csv",
        "Scenario": "ExportedMetadata_Scenario.csv",
        "Currency": "ExportedMetadata_Currency.csv",
        "Version": "ExportedMetadata_Version.csv",
        "Future1": "ExportedMetadata_Future1.csv",
    }

    for dimension, filename in dimension_files.items():
        filepath = data_dir / filename
        if not filepath.exists():
            continue

        members = []
        try:
            with open(filepath, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                header = next(reader, None)  # Skip header row

                for row in reader:
                    if not row or not row[0]:
                        continue

                    member_name = row[0].strip()
                    parent = row[1].strip() if len(row) > 1 and row[1] else None

                    # Get alias from "Alias: Default" column (typically column 2 or 3)
                    alias = None
                    if len(row) > 2 and row[2]:
                        alias = row[2].strip()
                        if alias == member_name or not alias:
                            alias = None

                    members.append({
                        "name": member_name,
                        "parent": parent,
                        "alias": alias
                    })

            if members:
                count = svc.index_members_batch(dimension, members)
                results[dimension] = count

        except Exception as e:
            import sys
            print(f"Warning: Error indexing {dimension} from {filepath}: {e}", file=sys.stderr)

    return results
