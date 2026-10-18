"""Contextual Memory Engine for Alexa+.

Provides persistent multi-session memory, user profile management,
hierarchical preferences, conversation history tracking, and dynamic
context summary generation for LLM prompting.
"""

import os
import sys
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

from sqlalchemy import Column, String, Text, DateTime, Integer, JSON, desc, func, distinct

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from config.database import Base, engine, get_db_session

logger = logging.getLogger("memory_engine")


# ==============================================================================
# SQLAlchemy Memory Models
# ==============================================================================

class UserProfile(Base):
    """User profile model containing personal info, preferences, and assistant persona notes."""
    __tablename__ = "user_profiles"

    user_id = Column(String(128), primary_key=True)
    display_name = Column(String(128), nullable=True)
    preferences = Column(JSON, nullable=False, default=dict)
    personality_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self) -> Dict[str, Any]:
        """Convert UserProfile record to dictionary."""
        return {
            "user_id": self.user_id,
            "display_name": self.display_name or self.user_id,
            "preferences": self.preferences or {},
            "personality_notes": self.personality_notes or "",
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ConversationHistory(Base):
    """Multi-turn conversation history recording interactions, intents, and tool calls."""
    __tablename__ = "conversation_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(128), nullable=False, index=True)
    session_id = Column(String(128), nullable=True, index=True)
    role = Column(String(32), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    intent_name = Column(String(128), nullable=True)
    tool_used = Column(String(128), nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    def to_dict(self) -> Dict[str, Any]:
        """Convert ConversationHistory record to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "intent_name": self.intent_name,
            "tool_used": self.tool_used,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class UserPreference(Base):
    """Categorized preference store for granular user personalization."""
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(128), nullable=False, index=True)
    preference_key = Column(String(128), nullable=False, index=True)
    preference_value = Column(Text, nullable=False)
    category = Column(String(64), nullable=False, default="general", index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self) -> Dict[str, Any]:
        """Convert UserPreference record to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "preference_key": self.preference_key,
            "preference_value": self.preference_value,
            "category": self.category,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


def init_memory_tables() -> None:
    """Create all memory tables in the SQL database."""
    logger.info("Initializing Contextual Memory Engine tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Memory database tables created successfully.")


# ==============================================================================
# Memory Engine Implementation
# ==============================================================================

class MemoryEngine:
    """Manages persistent context, conversational memory, and preferences for a user."""

    def __init__(self, user_id: str):
        """Initialize MemoryEngine bound to a specific user ID."""
        if not user_id or not isinstance(user_id, str):
            raise ValueError("user_id must be a non-empty string.")
        self.user_id = user_id.strip()

    def get_or_create_profile(self, display_name: Optional[str] = None) -> Dict[str, Any]:
        """Retrieve existing user profile or create a default profile."""
        with get_db_session() as db:
            profile = db.query(UserProfile).filter(UserProfile.user_id == self.user_id).first()
            if not profile:
                profile = UserProfile(
                    user_id=self.user_id,
                    display_name=display_name or self.user_id,
                    preferences={},
                    personality_notes="",
                )
                db.add(profile)
                db.flush()
                logger.info(f"Created new user profile for '{self.user_id}'.")
            return profile.to_dict()

    def update_preferences(self, preferences: Dict[str, Any], category: str = "general") -> Dict[str, Any]:
        """Merge a dictionary of preferences into the profile and preference tables."""
        with get_db_session() as db:
            profile = db.query(UserProfile).filter(UserProfile.user_id == self.user_id).first()
            if not profile:
                profile = UserProfile(user_id=self.user_id, preferences={})
                db.add(profile)
            current_prefs = dict(profile.preferences or {})
            for key, val in preferences.items():
                str_val = str(val)
                current_prefs[key] = val
                pref = db.query(UserPreference).filter(
                    UserPreference.user_id == self.user_id, UserPreference.preference_key == key
                ).first()
                if pref:
                    pref.preference_value, pref.category = str_val, category
                    pref.updated_at = datetime.now(timezone.utc)
                else:
                    db.add(UserPreference(user_id=self.user_id, preference_key=key, preference_value=str_val, category=category))
            profile.preferences = current_prefs
            profile.updated_at = datetime.now(timezone.utc)
            db.flush()
            return dict(profile.preferences)

    def set_preference(self, key: str, value: str, category: str = "general") -> Dict[str, Any]:
        """Set a single preference in both UserPreference and UserProfile stores."""
        with get_db_session() as db:
            profile = db.query(UserProfile).filter(UserProfile.user_id == self.user_id).first()
            if not profile:
                profile = UserProfile(user_id=self.user_id, preferences={})
                db.add(profile)
            current_prefs = dict(profile.preferences or {})
            current_prefs[key] = value
            profile.preferences = current_prefs
            profile.updated_at = datetime.now(timezone.utc)

            pref = db.query(UserPreference).filter(
                UserPreference.user_id == self.user_id, UserPreference.preference_key == key
            ).first()
            if pref:
                pref.preference_value, pref.category = str(value), category
                pref.updated_at = datetime.now(timezone.utc)
            else:
                pref = UserPreference(user_id=self.user_id, preference_key=key, preference_value=str(value), category=category)
                db.add(pref)
            db.flush()
            return pref.to_dict()

    def get_preference(self, key: str) -> Optional[str]:
        """Retrieve a single preference value by key."""
        with get_db_session() as db:
            pref = db.query(UserPreference).filter(
                UserPreference.user_id == self.user_id, UserPreference.preference_key == key
            ).first()
            if pref:
                return pref.preference_value
            profile = db.query(UserProfile).filter(UserProfile.user_id == self.user_id).first()
            return str(profile.preferences[key]) if profile and profile.preferences and key in profile.preferences else None

    def get_preferences_by_category(self, category: str) -> Dict[str, str]:
        """Get all preferences belonging to a specific category."""
        with get_db_session() as db:
            records = db.query(UserPreference).filter(
                UserPreference.user_id == self.user_id, UserPreference.category == category
            ).all()
            return {rec.preference_key: rec.preference_value for rec in records}

    def save_conversation_turn(
        self,
        session_id: Optional[str],
        role: str,
        content: str,
        intent_name: Optional[str] = None,
        tool_used: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record an interaction turn in the conversation history."""
        with get_db_session() as db:
            turn = ConversationHistory(
                user_id=self.user_id,
                session_id=session_id,
                role=role.lower(),
                content=content,
                intent_name=intent_name,
                tool_used=tool_used,
            )
            db.add(turn)
            db.flush()
            return turn.to_dict()

    def get_recent_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get the most recent conversation turns for this user in chronological order."""
        with get_db_session() as db:
            turns = db.query(ConversationHistory).filter(
                ConversationHistory.user_id == self.user_id
            ).order_by(desc(ConversationHistory.timestamp)).limit(limit).all()
            return [turn.to_dict() for turn in reversed(turns)]

    def get_session_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all conversation turns for a specific session in chronological order."""
        with get_db_session() as db:
            turns = db.query(ConversationHistory).filter(
                ConversationHistory.user_id == self.user_id, ConversationHistory.session_id == session_id
            ).order_by(ConversationHistory.timestamp.asc()).all()
            return [turn.to_dict() for turn in turns]

    def build_context_summary(self) -> str:
        """Construct a natural language context summary for LLM prompt augmentation."""
        profile = self.get_or_create_profile()
        stats = self.get_interaction_stats()
        lines = [f"User Identity: {profile.get('display_name', self.user_id)} (ID: {self.user_id})"]
        if profile.get("personality_notes"):
            lines.append(f"Persona & Style Notes: {profile['personality_notes']}")

        prefs = profile.get("preferences", {})
        lines.append(
            f"Known User Preferences: {', '.join([f'{k}: {v}' for k, v in prefs.items()])}"
            if prefs else "Known User Preferences: None recorded yet"
        )
        lines.append(f"Interaction Overview: {stats['total_turns']} total turns across {stats['session_count']} sessions.")
        if stats.get("top_intents"):
            lines.append(f"Frequent Intents: {', '.join([f'{k} ({v}x)' for k, v in stats['top_intents'].items()])}")
        if stats.get("top_tools"):
            lines.append(f"Preferred Tools: {', '.join([f'{k} ({v}x)' for k, v in stats['top_tools'].items()])}")

        recent = self.get_recent_history(limit=3)
        if recent:
            lines.append("Recent Dialogue Excerpt:")
            for turn in recent:
                lines.append(f"  - {turn['role'].capitalize()}: {turn['content'][:80]}")
        return "\n".join(lines)

    def get_interaction_stats(self) -> Dict[str, Any]:
        """Compute interaction analytics and preference metrics for the user."""
        with get_db_session() as db:
            total_turns = db.query(ConversationHistory).filter(ConversationHistory.user_id == self.user_id).count()
            user_turns = db.query(ConversationHistory).filter(
                ConversationHistory.user_id == self.user_id, ConversationHistory.role == "user"
            ).count()
            session_count = (
                db.query(func.count(distinct(ConversationHistory.session_id)))
                .filter(ConversationHistory.user_id == self.user_id, ConversationHistory.session_id.isnot(None))
                .scalar() or 0
            )
            intents_q = (
                db.query(ConversationHistory.intent_name, func.count(ConversationHistory.id))
                .filter(ConversationHistory.user_id == self.user_id, ConversationHistory.intent_name.isnot(None))
                .group_by(ConversationHistory.intent_name)
                .order_by(desc(func.count(ConversationHistory.id))).limit(5).all()
            )
            tools_q = (
                db.query(ConversationHistory.tool_used, func.count(ConversationHistory.id))
                .filter(ConversationHistory.user_id == self.user_id, ConversationHistory.tool_used.isnot(None))
                .group_by(ConversationHistory.tool_used)
                .order_by(desc(func.count(ConversationHistory.id))).limit(5).all()
            )
            cats_q = db.query(UserPreference.category).filter(UserPreference.user_id == self.user_id).distinct().all()
            first_turn = db.query(ConversationHistory.timestamp).filter(ConversationHistory.user_id == self.user_id).order_by(ConversationHistory.timestamp.asc()).first()
            last_turn = db.query(ConversationHistory.timestamp).filter(ConversationHistory.user_id == self.user_id).order_by(ConversationHistory.timestamp.desc()).first()

            return {
                "total_turns": total_turns,
                "user_turns": user_turns,
                "assistant_turns": total_turns - user_turns,
                "session_count": session_count,
                "top_intents": {item[0]: item[1] for item in intents_q if item[0]},
                "top_tools": {item[0]: item[1] for item in tools_q if item[0]},
                "favorite_categories": [cat[0] for cat in cats_q if cat[0]],
                "first_interaction": first_turn[0].isoformat() if first_turn else None,
                "last_interaction": last_turn[0].isoformat() if last_turn else None,
            }

    def clear_history(self, older_than_days: int = 30) -> int:
        """Purge conversation history older than specified days for this user."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        with get_db_session() as db:
            deleted = (
                db.query(ConversationHistory)
                .filter(ConversationHistory.user_id == self.user_id, ConversationHistory.timestamp < cutoff)
                .delete(synchronize_session=False)
            )
            logger.info(f"Purged {deleted} turns older than {older_than_days}d for user '{self.user_id}'.")
            return deleted

# ==============================================================================
# Standalone Verification and Demonstration Block
# ==============================================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    print("=" * 60 + "\nALEXA+ CONTEXTUAL MEMORY ENGINE DEMONSTRATION\n" + "=" * 60)
    init_memory_tables()
    memory = MemoryEngine("amzn1.ask.account.DEMO_USER_001")
    profile = memory.get_or_create_profile(display_name="Devin Carter")
    print(f"\n[1] Profile: {profile['display_name']} (ID: {profile['user_id']})")
    memory.set_preference("speech_speed", "1.1x", category="voice")
    memory.set_preference("news_source", "reuters", category="content")
    memory.update_preferences({"temperature_unit": "fahrenheit", "home_city": "Seattle"}, category="general")
    print(f"[2] news_source preference: {memory.get_preference('news_source')}")
    print(f"[3] content preferences: {memory.get_preferences_by_category('content')}")
    memory.save_conversation_turn("sess_001", "user", "Alexa, what's my schedule?", "GetScheduleIntent")
    memory.save_conversation_turn("sess_001", "assistant", "You have 3 meetings today.", "GetScheduleIntent", "calendar_sync_tool")
    memory.save_conversation_turn("sess_001", "user", "Book a table for two at 7 PM.", "BookTableIntent")
    memory.save_conversation_turn("sess_001", "assistant", "Reserved a table at The Grill.", "BookTableIntent", "table_booking_tool")
    recent = memory.get_recent_history(limit=4)
    print(f"\n[4] Recent History ({len(recent)} turns):")
    for turn in recent:
        tool = f" [Tool: {turn['tool_used']}]" if turn.get("tool_used") else ""
        print(f"    - {turn['role'].upper()}: {turn['content']}{tool}")
    stats = memory.get_interaction_stats()
    print(f"\n[5] Stats: {stats['total_turns']} turns, {stats['session_count']} sessions, Top intents: {stats['top_intents']}")
    print("\n[6] Dynamic Context Summary for LLM:\n" + "-" * 50)
    print(memory.build_context_summary())
    print("-" * 50 + "\nContextual Memory Engine test completed successfully!")
