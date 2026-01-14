"""Enhanced Metadata Cache with Semantic Matching for EPM Planning.

This module provides:
1. Fast loading of dimension metadata from CSV exports
2. Fuzzy/semantic member matching
3. Hierarchy traversal utilities
4. Valid intersection discovery support
"""

import csv
import json
import sqlite3
from pathlib import Path
from typing import Any, Optional, List, Dict, Tuple
from difflib import SequenceMatcher
import re

# Project root for metadata files
PROJECT_ROOT = Path(__file__).parent.parent.parent
METADATA_DB = PROJECT_ROOT / ".cache" / "metadata.db"


class MetadataCache:
    """SQLite-backed metadata cache for fast semantic matching."""
    
    def __init__(self):
        self.db_path = METADATA_DB
        self._ensure_db()
    
    def _ensure_db(self):
        """Create database and tables if not exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dimension TEXT NOT NULL,
                    member_name TEXT NOT NULL,
                    parent TEXT,
                    alias TEXT,
                    description TEXT,
                    data_storage TEXT,
                    account_type TEXT,
                    level INTEGER DEFAULT 0,
                    is_leaf INTEGER DEFAULT 1,
                    UNIQUE(dimension, member_name)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_dimension ON members(dimension)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_member_name ON members(member_name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_alias ON members(alias)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_parent ON members(parent)")
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS valid_intersections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity TEXT NOT NULL,
                    cost_center TEXT,
                    region TEXT,
                    account TEXT,
                    has_data INTEGER DEFAULT 0,
                    last_checked TEXT,
                    UNIQUE(entity, cost_center, region, account)
                )
            """)

            # Flexible valid intersections table for any dimension combination
            conn.execute("""
                CREATE TABLE IF NOT EXISTS valid_intersection_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rule_name TEXT NOT NULL,
                    dimensions TEXT NOT NULL,
                    members_json TEXT NOT NULL,
                    is_valid INTEGER DEFAULT 1,
                    has_data INTEGER DEFAULT 0,
                    sample_value TEXT,
                    last_checked TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(rule_name, members_json)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_rule_name ON valid_intersection_rules(rule_name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_dimensions ON valid_intersection_rules(dimensions)")

            # Valid intersection groups metadata
            conn.execute("""
                CREATE TABLE IF NOT EXISTS valid_intersection_groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    dimensions TEXT NOT NULL,
                    enabled INTEGER DEFAULT 1,
                    source TEXT DEFAULT 'discovered',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT
                )
            """)
            conn.commit()
    
    def load_dimension_from_csv(self, dimension: str, csv_path: Optional[Path] = None) -> int:
        """Load dimension members from CSV export file."""
        if csv_path is None:
            # Check both root and data subdirectory
            csv_path = PROJECT_ROOT / f"ExportedMetadata_{dimension}.csv"
            if not csv_path.exists():
                csv_path = PROJECT_ROOT / "data" / f"ExportedMetadata_{dimension}.csv"
        
        if not csv_path.exists():
            return 0
        
        members = []
        encodings = ["utf-8-sig", "utf-8", "latin-1", "cp1252"]
        
        for encoding in encodings:
            try:
                with open(csv_path, "r", encoding=encoding) as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        member_name = row.get(dimension, "").strip()
                        if not member_name or member_name == dimension:
                            continue
                        
                        # Handle space-prefixed column names
                        parent = row.get(" Parent", row.get("Parent", "")).strip()
                        alias = row.get(" Alias: Default", row.get("Alias: Default", "")).strip()
                        description = row.get(" Description", row.get("Description", "")).strip()
                        data_storage = row.get(" Data Storage", row.get("Data Storage", "")).strip()
                        account_type = row.get(" Account Type", row.get("Account Type", "")).strip()
                        
                        members.append({
                            "dimension": dimension,
                            "member_name": member_name,
                            "parent": parent if parent else None,
                            "alias": alias if alias else None,
                            "description": description if description else None,
                            "data_storage": data_storage if data_storage else None,
                            "account_type": account_type if account_type else None,
                        })
                break
            except Exception:
                continue
        
        if not members:
            return 0
        
        # Calculate levels and leaf status
        parent_map = {m["member_name"]: m["parent"] for m in members}
        has_children = set(m["parent"] for m in members if m["parent"])
        
        def get_level(member_name: str, visited: set = None) -> int:
            if visited is None:
                visited = set()
            if member_name in visited:
                return 0
            visited.add(member_name)
            parent = parent_map.get(member_name)
            if not parent or parent == dimension:
                return 0
            return 1 + get_level(parent, visited)
        
        for m in members:
            m["level"] = get_level(m["member_name"])
            m["is_leaf"] = 1 if m["member_name"] not in has_children else 0
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM members WHERE dimension = ?", (dimension,))
            conn.executemany("""
                INSERT OR REPLACE INTO members 
                (dimension, member_name, parent, alias, description, data_storage, account_type, level, is_leaf)
                VALUES (:dimension, :member_name, :parent, :alias, :description, :data_storage, :account_type, :level, :is_leaf)
            """, members)
            conn.commit()
        
        return len(members)
    
    def load_all_dimensions(self) -> Dict[str, int]:
        """Load all available dimension CSVs into cache."""
        dimensions = ["Account", "Entity", "CostCenter", "Region", "Scenario", "Version", "Currency", "Future1"]
        results = {}
        for dim in dimensions:
            count = self.load_dimension_from_csv(dim)
            if count > 0:
                results[dim] = count
        return results
    
    def semantic_search(self, search_term: str, dimension: Optional[str] = None, limit: int = 10, min_score: float = 0.4) -> List[Dict[str, Any]]:
        """Search for members using fuzzy/semantic matching."""
        search_lower = search_term.lower().strip()
        search_normalized = re.sub(r'[^a-z0-9]', '', search_lower)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if dimension:
                rows = conn.execute("SELECT * FROM members WHERE dimension = ?", (dimension,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM members").fetchall()
        
        results = []
        for row in rows:
            member_name = row["member_name"]
            alias = row["alias"] or ""
            description = row["description"] or ""
            
            scores = []
            
            if search_lower == member_name.lower():
                scores.append(1.0)
            elif search_lower == alias.lower():
                scores.append(0.98)
            
            member_normalized = re.sub(r'[^a-z0-9]', '', member_name.lower())
            if search_normalized == member_normalized:
                scores.append(0.95)
            
            if search_lower in member_name.lower():
                scores.append(0.85)
            if search_lower in alias.lower():
                scores.append(0.80)
            if search_lower in description.lower():
                scores.append(0.70)
            
            name_score = SequenceMatcher(None, search_lower, member_name.lower()).ratio()
            alias_score = SequenceMatcher(None, search_lower, alias.lower()).ratio() if alias else 0
            
            if name_score > min_score:
                scores.append(name_score * 0.9)
            if alias_score > min_score:
                scores.append(alias_score * 0.85)
            
            search_words = search_lower.split()
            if len(search_words) > 1:
                member_words = member_name.lower().split()
                alias_words = alias.lower().split() if alias else []
                matching_words = sum(1 for w in search_words if any(w in mw for mw in member_words + alias_words))
                if matching_words > 0:
                    scores.append(matching_words / len(search_words) * 0.75)
            
            if scores:
                best_score = max(scores)
                if best_score >= min_score:
                    results.append({
                        "member_name": member_name,
                        "dimension": row["dimension"],
                        "alias": alias,
                        "description": description,
                        "parent": row["parent"],
                        "data_storage": row["data_storage"],
                        "level": row["level"],
                        "is_leaf": bool(row["is_leaf"]),
                        "confidence": round(best_score, 3),
                        "match_type": "exact" if best_score >= 0.95 else "contains" if best_score >= 0.7 else "fuzzy"
                    })
        
        results.sort(key=lambda x: x["confidence"], reverse=True)
        return results[:limit]
    
    def get_children(self, dimension: str, parent: str) -> List[Dict[str, Any]]:
        """Get direct children of a member."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM members WHERE dimension = ? AND parent = ? ORDER BY member_name", (dimension, parent)).fetchall()
        return [dict(row) for row in rows]
    
    def get_ancestors(self, dimension: str, member: str) -> List[str]:
        """Get path from member to root."""
        ancestors = []
        current = member
        with sqlite3.connect(self.db_path) as conn:
            while current:
                row = conn.execute("SELECT parent FROM members WHERE dimension = ? AND member_name = ?", (dimension, current)).fetchone()
                if row and row[0] and row[0] != dimension:
                    ancestors.append(row[0])
                    current = row[0]
                else:
                    break
        return ancestors
    
    def get_leaves(self, dimension: str, parent: Optional[str] = None) -> List[str]:
        """Get all leaf members."""
        with sqlite3.connect(self.db_path) as conn:
            if parent:
                descendants = self._get_all_descendants(dimension, parent)
                if descendants:
                    placeholders = ','.join('?' * len(descendants))
                    rows = conn.execute(f"SELECT member_name FROM members WHERE dimension = ? AND is_leaf = 1 AND member_name IN ({placeholders})", (dimension, *descendants)).fetchall()
                else:
                    rows = []
            else:
                rows = conn.execute("SELECT member_name FROM members WHERE dimension = ? AND is_leaf = 1", (dimension,)).fetchall()
        return [row[0] for row in rows]
    
    def _get_all_descendants(self, dimension: str, parent: str) -> List[str]:
        """Get all descendants of a member."""
        descendants = []
        to_process = [parent]
        with sqlite3.connect(self.db_path) as conn:
            while to_process:
                current = to_process.pop(0)
                children = conn.execute("SELECT member_name FROM members WHERE dimension = ? AND parent = ?", (dimension, current)).fetchall()
                for child in children:
                    descendants.append(child[0])
                    to_process.append(child[0])
        return descendants
    
    def get_member_info(self, dimension: str, member: str) -> Optional[Dict[str, Any]]:
        """Get full info for a specific member."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM members WHERE dimension = ? AND member_name = ?", (dimension, member)).fetchone()
        return dict(row) if row else None
    
    def resolve_member(self, search_term: str, dimension: str) -> Optional[str]:
        """Resolve a search term to an exact member name."""
        results = self.semantic_search(search_term, dimension=dimension, limit=1, min_score=0.5)
        if results and results[0]["confidence"] >= 0.5:
            return results[0]["member_name"]
        return None
    
    def save_valid_intersection(self, entity: str, cost_center: str, region: str, account: Optional[str] = None, has_data: bool = True):
        """Save a known valid intersection."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO valid_intersections 
                (entity, cost_center, region, account, has_data, last_checked)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
            """, (entity, cost_center, region, account, 1 if has_data else 0))
            conn.commit()
    
    def get_valid_intersections(self, entity: Optional[str] = None, cost_center: Optional[str] = None, region: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get known valid intersections with optional filters."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            conditions = ["has_data = 1"]
            params = []
            if entity:
                conditions.append("entity = ?")
                params.append(entity)
            if cost_center:
                conditions.append("cost_center = ?")
                params.append(cost_center)
            if region:
                conditions.append("region = ?")
                params.append(region)
            rows = conn.execute(f"SELECT * FROM valid_intersections WHERE {' AND '.join(conditions)}", params).fetchall()
        return [dict(row) for row in rows]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with sqlite3.connect(self.db_path) as conn:
            stats = {}
            rows = conn.execute("SELECT dimension, COUNT(*) as count, SUM(is_leaf) as leaf_count FROM members GROUP BY dimension").fetchall()
            stats["dimensions"] = {row[0]: {"total": row[1], "leaves": row[2]} for row in rows}
            row = conn.execute("SELECT COUNT(*) FROM valid_intersections WHERE has_data = 1").fetchone()
            stats["valid_intersections"] = row[0]
            row = conn.execute("SELECT COUNT(*) FROM valid_intersection_rules WHERE is_valid = 1").fetchone()
            stats["valid_intersection_rules"] = row[0] if row else 0
            row = conn.execute("SELECT COUNT(*) FROM valid_intersection_groups").fetchone()
            stats["valid_intersection_groups"] = row[0] if row else 0
        return stats

    # ========== Flexible Valid Intersection Methods ==========

    def save_intersection_rule(
        self,
        rule_name: str,
        members: Dict[str, str],
        is_valid: bool = True,
        has_data: bool = False,
        sample_value: Optional[str] = None
    ):
        """Save a flexible valid intersection rule.

        Args:
            rule_name: Name of the intersection rule/group.
            members: Dictionary mapping dimension names to member names.
            is_valid: Whether this intersection is valid.
            has_data: Whether this intersection has data.
            sample_value: Optional sample value found at this intersection.
        """
        dimensions = ",".join(sorted(members.keys()))
        members_json = json.dumps(members, sort_keys=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO valid_intersection_rules
                (rule_name, dimensions, members_json, is_valid, has_data, sample_value, last_checked)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            """, (rule_name, dimensions, members_json, 1 if is_valid else 0, 1 if has_data else 0, sample_value))
            conn.commit()

    def get_intersection_rules(
        self,
        rule_name: Optional[str] = None,
        dimensions: Optional[List[str]] = None,
        only_valid: bool = True,
        only_with_data: bool = False
    ) -> List[Dict[str, Any]]:
        """Get flexible valid intersection rules.

        Args:
            rule_name: Filter by rule name.
            dimensions: Filter by dimensions involved.
            only_valid: Only return valid intersections.
            only_with_data: Only return intersections with data.

        Returns:
            List of intersection rules.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            conditions = []
            params = []

            if rule_name:
                conditions.append("rule_name = ?")
                params.append(rule_name)
            if dimensions:
                dim_str = ",".join(sorted(dimensions))
                conditions.append("dimensions = ?")
                params.append(dim_str)
            if only_valid:
                conditions.append("is_valid = 1")
            if only_with_data:
                conditions.append("has_data = 1")

            where_clause = " AND ".join(conditions) if conditions else "1=1"
            rows = conn.execute(
                f"SELECT * FROM valid_intersection_rules WHERE {where_clause} ORDER BY last_checked DESC",
                params
            ).fetchall()

        results = []
        for row in rows:
            result = dict(row)
            result["members"] = json.loads(result["members_json"])
            del result["members_json"]
            result["is_valid"] = bool(result["is_valid"])
            result["has_data"] = bool(result["has_data"])
            results.append(result)

        return results

    def check_intersection_rule(
        self,
        members: Dict[str, str],
        rule_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Check if a specific member combination exists in rules.

        Args:
            members: Dictionary mapping dimension names to member names.
            rule_name: Optional rule name to filter by.

        Returns:
            The matching rule if found, None otherwise.
        """
        members_json = json.dumps(members, sort_keys=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if rule_name:
                row = conn.execute(
                    "SELECT * FROM valid_intersection_rules WHERE rule_name = ? AND members_json = ?",
                    (rule_name, members_json)
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM valid_intersection_rules WHERE members_json = ?",
                    (members_json,)
                ).fetchone()

        if row:
            result = dict(row)
            result["members"] = json.loads(result["members_json"])
            del result["members_json"]
            result["is_valid"] = bool(result["is_valid"])
            result["has_data"] = bool(result["has_data"])
            return result
        return None

    def save_intersection_group(
        self,
        group_name: str,
        dimensions: List[str],
        description: Optional[str] = None,
        enabled: bool = True,
        source: str = "discovered"
    ):
        """Save a valid intersection group definition.

        Args:
            group_name: Unique name for the group.
            dimensions: List of dimension names in the group.
            description: Optional description of the group.
            enabled: Whether the group is enabled.
            source: Source of the group (discovered, imported, manual).
        """
        dimensions_str = ",".join(sorted(dimensions))

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO valid_intersection_groups
                (group_name, description, dimensions, enabled, source, updated_at)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
            """, (group_name, description, dimensions_str, 1 if enabled else 0, source))
            conn.commit()

    def get_intersection_groups(self, only_enabled: bool = True) -> List[Dict[str, Any]]:
        """Get all valid intersection groups.

        Args:
            only_enabled: Only return enabled groups.

        Returns:
            List of intersection groups.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if only_enabled:
                rows = conn.execute(
                    "SELECT * FROM valid_intersection_groups WHERE enabled = 1 ORDER BY group_name"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM valid_intersection_groups ORDER BY group_name"
                ).fetchall()

        results = []
        for row in rows:
            result = dict(row)
            result["dimensions"] = result["dimensions"].split(",")
            result["enabled"] = bool(result["enabled"])
            results.append(result)

        return results

    def delete_intersection_rules(
        self,
        rule_name: Optional[str] = None,
        older_than_days: Optional[int] = None
    ) -> int:
        """Delete intersection rules.

        Args:
            rule_name: Delete rules with this name.
            older_than_days: Delete rules older than this many days.

        Returns:
            Number of rows deleted.
        """
        with sqlite3.connect(self.db_path) as conn:
            if rule_name and older_than_days:
                result = conn.execute(
                    "DELETE FROM valid_intersection_rules WHERE rule_name = ? AND last_checked < datetime('now', ?)",
                    (rule_name, f"-{older_than_days} days")
                )
            elif rule_name:
                result = conn.execute(
                    "DELETE FROM valid_intersection_rules WHERE rule_name = ?",
                    (rule_name,)
                )
            elif older_than_days:
                result = conn.execute(
                    "DELETE FROM valid_intersection_rules WHERE last_checked < datetime('now', ?)",
                    (f"-{older_than_days} days",)
                )
            else:
                result = conn.execute("DELETE FROM valid_intersection_rules")
            conn.commit()
            return result.rowcount


_cache: Optional[MetadataCache] = None

def get_metadata_cache() -> MetadataCache:
    """Get or create the singleton metadata cache."""
    global _cache
    if _cache is None:
        _cache = MetadataCache()
    return _cache
