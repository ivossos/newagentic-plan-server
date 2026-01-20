"""Personalization Service - Onboarding checklist and user preferences."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


class PersonalizationChecklist(Base):
    """Track personalization/onboarding checklist items."""

    __tablename__ = "personalization_checklist"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(100), index=True, default="default")
    item_key = Column(String(100), nullable=False, index=True)
    item_label = Column(String(255), nullable=False)
    item_description = Column(String(500), nullable=True)
    is_done = Column(Boolean, default=False)
    value = Column(JSON, nullable=True)  # Store item value/response
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserPreference(Base):
    """Store user preferences."""

    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(100), index=True, default="default")
    preference_key = Column(String(100), nullable=False, index=True)
    preference_value = Column(JSON, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Default Planning checklist items
DEFAULT_CHECKLIST_ITEMS = [
    {
        "key": "app_name",
        "label": "Application Name",
        "description": "Confirm the Oracle Planning application name (e.g., PlanApp, FinPlan)"
    },
    {
        "key": "cube",
        "label": "Plan Type / Cube",
        "description": "Confirm the plan type or cube to use (e.g., OEP_FS, OEP_WFP, FinPlan, FinRPT)"
    },
    {
        "key": "pov_defaults",
        "label": "Default POV Settings",
        "description": "Confirm default Point of View settings (Entity, Scenario, Year, Version)"
    },
    {
        "key": "dimensions",
        "label": "Key Dimensions",
        "description": "Confirm key dimensions to work with (Account, Entity, Scenario, Period, etc.)"
    },
    {
        "key": "language",
        "label": "Preferred Language",
        "description": "Confirm preferred language for responses (English, Portuguese, etc.)"
    },
    {
        "key": "reporting",
        "label": "Reporting Preferences",
        "description": "Confirm reporting output format and preferences (Word, Excel, PDF)"
    },
]


@dataclass
class ChecklistStatus:
    """Status of personalization checklist."""

    total_items: int = 0
    completed_items: int = 0
    progress_percent: float = 0.0
    items: list[dict[str, Any]] = field(default_factory=list)
    is_complete: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_items": self.total_items,
            "completed_items": self.completed_items,
            "progress_percent": self.progress_percent,
            "items": self.items,
            "is_complete": self.is_complete
        }


class PersonalizationService:
    """Service for managing user personalization and onboarding."""

    def __init__(self, db_url: str):
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def ensure_checklist(self, user_id: str = "default") -> None:
        """Ensure all default checklist items exist for user."""
        with self.Session() as session:
            for item in DEFAULT_CHECKLIST_ITEMS:
                existing = session.query(PersonalizationChecklist).filter(
                    PersonalizationChecklist.user_id == user_id,
                    PersonalizationChecklist.item_key == item["key"]
                ).first()

                if not existing:
                    checklist_item = PersonalizationChecklist(
                        user_id=user_id,
                        item_key=item["key"],
                        item_label=item["label"],
                        item_description=item["description"],
                        is_done=False
                    )
                    session.add(checklist_item)

            session.commit()

    def get_status(self, user_id: str = "default") -> ChecklistStatus:
        """Get the current checklist status for a user."""
        self.ensure_checklist(user_id)

        with self.Session() as session:
            items = session.query(PersonalizationChecklist).filter(
                PersonalizationChecklist.user_id == user_id
            ).all()

            item_list = []
            completed = 0

            for item in items:
                item_dict = {
                    "key": item.item_key,
                    "label": item.item_label,
                    "description": item.item_description,
                    "is_done": item.is_done,
                    "value": item.value
                }
                item_list.append(item_dict)
                if item.is_done:
                    completed += 1

            total = len(item_list)
            progress = (completed / total * 100) if total > 0 else 0

            return ChecklistStatus(
                total_items=total,
                completed_items=completed,
                progress_percent=round(progress, 1),
                items=item_list,
                is_complete=(completed == total and total > 0)
            )

    def update_item(
        self,
        item_key: str,
        is_done: bool = True,
        value: Any = None,
        user_id: str = "default"
    ) -> bool:
        """Update a checklist item.

        Args:
            item_key: The key of the checklist item
            is_done: Whether the item is complete
            value: Optional value/response for the item
            user_id: User identifier

        Returns:
            True if updated successfully
        """
        self.ensure_checklist(user_id)

        with self.Session() as session:
            item = session.query(PersonalizationChecklist).filter(
                PersonalizationChecklist.user_id == user_id,
                PersonalizationChecklist.item_key == item_key
            ).first()

            if item:
                item.is_done = is_done
                if value is not None:
                    item.value = value
                item.updated_at = datetime.utcnow()
                session.commit()
                return True

            return False

    def set_preference(
        self,
        preference_key: str,
        preference_value: Any,
        user_id: str = "default"
    ) -> bool:
        """Set a user preference.

        Args:
            preference_key: Preference identifier
            preference_value: Preference value (will be JSON serialized)
            user_id: User identifier

        Returns:
            True if set successfully
        """
        with self.Session() as session:
            existing = session.query(UserPreference).filter(
                UserPreference.user_id == user_id,
                UserPreference.preference_key == preference_key
            ).first()

            if existing:
                existing.preference_value = preference_value
                existing.updated_at = datetime.utcnow()
            else:
                pref = UserPreference(
                    user_id=user_id,
                    preference_key=preference_key,
                    preference_value=preference_value
                )
                session.add(pref)

            session.commit()
            return True

    def get_preference(
        self,
        preference_key: str,
        user_id: str = "default",
        default: Any = None
    ) -> Any:
        """Get a user preference.

        Args:
            preference_key: Preference identifier
            user_id: User identifier
            default: Default value if preference not found

        Returns:
            Preference value or default
        """
        with self.Session() as session:
            pref = session.query(UserPreference).filter(
                UserPreference.user_id == user_id,
                UserPreference.preference_key == preference_key
            ).first()

            return pref.preference_value if pref else default

    def get_all_preferences(self, user_id: str = "default") -> dict[str, Any]:
        """Get all preferences for a user."""
        with self.Session() as session:
            prefs = session.query(UserPreference).filter(
                UserPreference.user_id == user_id
            ).all()

            return {p.preference_key: p.preference_value for p in prefs}

    def set_app_name(self, app_name: str, user_id: str = "default") -> None:
        """Set the application name and mark checklist item as done."""
        self.update_item("app_name", is_done=True, value=app_name, user_id=user_id)
        self.set_preference("app_name", app_name, user_id=user_id)

    def get_pov_defaults(self, user_id: str = "default") -> dict[str, str]:
        """Get the default POV settings."""
        return self.get_preference("pov_defaults", user_id=user_id, default={
            "entity": "E501",
            "scenario": "Actual",
            "years": "FY25",
            "version": "Final",
            "period": "YearTotal",
            "currency": "USD",
            "cost_center": "CC9999",
            "future1": "Total Plan",
            "region": "R131"
        })


# Global state
_personalization_service: Optional[PersonalizationService] = None


def init_personalization_service(db_url: str) -> Optional[PersonalizationService]:
    """Initialize the global personalization service."""
    global _personalization_service
    try:
        _personalization_service = PersonalizationService(db_url)
        return _personalization_service
    except Exception as e:
        import sys
        print(f"Warning: Could not initialize personalization service: {e}", file=sys.stderr)
        return None


def get_personalization_service() -> Optional[PersonalizationService]:
    """Get the global personalization service instance."""
    return _personalization_service
