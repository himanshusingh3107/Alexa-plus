"""Database configuration, models, and SQL query helper functions.

Uses SQLAlchemy with native Python dictionary support (no manual json conversion needed).
Supports SQLite (default) and PostgreSQL with thread-safe connection pooling.
"""

import os
import uuid
import logging
from datetime import datetime, timezone
from contextlib import contextmanager
from typing import List, Dict, Any, Optional

from sqlalchemy import (
    create_engine,
    Column,
    String,
    Text,
    DateTime,
    Integer,
    JSON,
    desc,
)
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session

logger = logging.getLogger(__name__)

Base = declarative_base()


class TaskBooking(Base):
    """SQL table for booking management, voice tasks, and scheduled automations."""

    __tablename__ = "task_bookings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False)
    category = Column(String(64), nullable=False, default="booking")
    status = Column(String(32), nullable=False, default="pending")
    description = Column(Text, nullable=True)
    scheduled_time = Column(DateTime, nullable=True)
    # Native Python dictionary stored directly in SQL
    metadata_payload = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to clean Python dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "status": self.status,
            "description": self.description or "",
            "scheduled_time": self.scheduled_time.isoformat() if self.scheduled_time else None,
            "metadata": self.metadata_payload or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class LiveEventLog(Base):
    """SQL table for recording live execution logs, telemetry, and streaming events."""

    __tablename__ = "live_event_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=True, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    # Native Python dictionary stored directly in SQL
    details = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    def to_dict(self) -> Dict[str, Any]:
        """Convert log entry to pure Python dictionary."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "event_type": self.event_type,
            "details": self.details or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


from dotenv import load_dotenv
load_dotenv()

# Database engine & session setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///alexa_mcp.db")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN") or os.getenv("SECRET_KEY") or os.getenv("TURSO_TOKEN")

TURSO_CLIENT = None
TURSO_ENABLED = False

if DATABASE_URL.startswith("libsql://") or "turso.io" in DATABASE_URL or os.getenv("TURSO_DATABASE_URL"):
    TURSO_ENABLED = True
    turso_url = os.getenv("TURSO_DATABASE_URL") or (DATABASE_URL if "turso.io" in DATABASE_URL else "")
    if turso_url.startswith("libsql://"):
        turso_url = turso_url.replace("libsql://", "https://")
    if turso_url and not turso_url.startswith("http"):
        turso_url = f"https://{turso_url}"

    try:
        import libsql_client
        if turso_url and TURSO_AUTH_TOKEN:
            TURSO_CLIENT = libsql_client.create_client_sync(turso_url, auth_token=TURSO_AUTH_TOKEN)
            logger.info(f"Connected to Turso Cloud Database: {turso_url}")
    except Exception as exc:
        logger.warning(f"Turso client initialization skipped ({exc}). Operating in local SQLite mode.")

    sqlalchemy_url = "sqlite:///alexa_mcp.db"
else:
    sqlalchemy_url = DATABASE_URL

connect_args = {}
if sqlalchemy_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    sqlalchemy_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))


def init_turso_schema() -> None:
    """Ensure all required tables exist in Turso Cloud."""
    if not TURSO_CLIENT:
        return
    try:
        logger.info("Syncing tables with Turso Cloud Database...")
        TURSO_CLIENT.execute("""CREATE TABLE IF NOT EXISTS task_bookings (
            id VARCHAR(36) PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            category VARCHAR(64) NOT NULL DEFAULT 'booking',
            status VARCHAR(32) NOT NULL DEFAULT 'pending',
            description TEXT,
            scheduled_time DATETIME,
            metadata_payload JSON,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        )""")
        TURSO_CLIENT.execute("""CREATE TABLE IF NOT EXISTS live_event_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id VARCHAR(64),
            event_type VARCHAR(64) NOT NULL,
            details JSON NOT NULL,
            created_at DATETIME NOT NULL
        )""")
        TURSO_CLIENT.execute("""CREATE TABLE IF NOT EXISTS user_profiles (
            user_id VARCHAR(128) PRIMARY KEY,
            display_name VARCHAR(128),
            preferences JSON NOT NULL,
            personality_notes TEXT,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        )""")
        TURSO_CLIENT.execute("""CREATE TABLE IF NOT EXISTS conversation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id VARCHAR(128) NOT NULL,
            session_id VARCHAR(128),
            role VARCHAR(32) NOT NULL,
            content TEXT NOT NULL,
            intent_name VARCHAR(128),
            tool_used VARCHAR(128),
            timestamp DATETIME NOT NULL
        )""")
        TURSO_CLIENT.execute("""CREATE TABLE IF NOT EXISTS user_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id VARCHAR(128) NOT NULL,
            preference_key VARCHAR(128) NOT NULL,
            preference_value TEXT NOT NULL,
            category VARCHAR(64) NOT NULL DEFAULT 'general',
            updated_at DATETIME NOT NULL
        )""")
        logger.info("Turso Cloud Database schema verified & synced successfully.")
    except Exception as exc:
        logger.warning(f"Could not sync schema to Turso: {exc}")


def init_db() -> None:
    """Initialize SQL database tables locally and in Turso Cloud."""
    logger.info("Initializing SQL database schema...")
    Base.metadata.create_all(bind=engine)
    logger.info("Local SQL database schema initialized successfully.")
    if TURSO_ENABLED:
        init_turso_schema()


@contextmanager
def get_db_session():
    """Context manager for safe database transactions using pure Python."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.error(f"Database session error: {exc}", exc_info=True)
        raise
    finally:
        session.close()


# ==============================================================================
# Helper Functions for Action Writes (INSERT / UPDATE)
# ==============================================================================

def create_task_booking(
    title: str,
    category: str = "booking",
    status: str = "pending",
    description: Optional[str] = None,
    scheduled_time: Optional[datetime] = None,
    metadata: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Insert a new task or booking record using pure Python dicts."""
    with get_db_session() as db:
        booking = TaskBooking(
            title=title,
            category=category,
            status=status,
            description=description,
            scheduled_time=scheduled_time,
            metadata_payload=metadata or {},
        )
        db.add(booking)
        db.flush()

        event = LiveEventLog(
            session_id=session_id,
            event_type="TASK_CREATED",
            details={
                "booking_id": booking.id,
                "title": booking.title,
                "category": booking.category,
                "status": booking.status,
            },
        )
        db.add(event)
        result = booking.to_dict()

    if TURSO_CLIENT:
        try:
            import json
            TURSO_CLIENT.execute(
                "INSERT OR REPLACE INTO task_bookings (id, title, category, status, description, scheduled_time, metadata_payload, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    result["id"],
                    result["title"],
                    result["category"],
                    result["status"],
                    result.get("description") or "",
                    result.get("scheduled_time"),
                    json.dumps(result.get("metadata") or {}),
                    result["created_at"],
                    result["updated_at"],
                ]
            )
        except Exception as t_err:
            logger.warning(f"Turso task sync error: {t_err}")

    logger.info(f"Created task booking: {result['id']} - {result['title']}")
    return result


def update_task_booking(
    booking_id: str,
    status: Optional[str] = None,
    description: Optional[str] = None,
    metadata_patch: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Update an existing task or booking record using pure Python dicts."""
    with get_db_session() as db:
        booking = db.query(TaskBooking).filter(TaskBooking.id == booking_id).first()
        if not booking:
            logger.warning(f"Task booking {booking_id} not found.")
            return None

        if status:
            booking.status = status
        if description is not None:
            booking.description = description
        if metadata_patch:
            current_meta = dict(booking.metadata_payload or {})
            current_meta.update(metadata_patch)
            booking.metadata_payload = current_meta

        booking.updated_at = datetime.now(timezone.utc)
        db.flush()

        event = LiveEventLog(
            session_id=session_id,
            event_type="TASK_UPDATED",
            details={
                "booking_id": booking.id,
                "status": booking.status,
                "title": booking.title,
            },
        )
        db.add(event)
        result = booking.to_dict()

    if TURSO_CLIENT and result:
        try:
            import json
            TURSO_CLIENT.execute(
                "UPDATE task_bookings SET status = ?, description = ?, metadata_payload = ?, updated_at = ? WHERE id = ?",
                [
                    result["status"],
                    result.get("description") or "",
                    json.dumps(result.get("metadata") or {}),
                    result["updated_at"],
                    result["id"],
                ]
            )
        except Exception as t_err:
            logger.warning(f"Turso update sync error: {t_err}")

    logger.info(f"Updated task booking {booking_id} to status {status}")
    return result


def record_live_event(
    event_type: str,
    details: Dict[str, Any],
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Insert a live system event using pure Python dictionaries."""
    with get_db_session() as db:
        event = LiveEventLog(
            session_id=session_id,
            event_type=event_type,
            details=details,
        )
        db.add(event)
        db.flush()
        result = event.to_dict()

    if TURSO_CLIENT and result:
        try:
            import json
            TURSO_CLIENT.execute(
                "INSERT INTO live_event_logs (session_id, event_type, details, created_at) VALUES (?, ?, ?, ?)",
                [
                    result.get("session_id"),
                    result["event_type"],
                    json.dumps(result.get("details") or {}),
                    result["created_at"],
                ]
            )
        except Exception as t_err:
            logger.warning(f"Turso event sync error: {t_err}")

    logger.debug(f"Recorded live event {event_type} (ID: {result['id']})")
    return result


# ==============================================================================
# Helper Functions for Action Reads (SELECT Queries)
# ==============================================================================

def query_task_bookings(
    status: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Query task bookings and return list of Python dictionaries."""
    with get_db_session() as db:
        query = db.query(TaskBooking)
        if status:
            query = query.filter(TaskBooking.status == status)
        if category:
            query = query.filter(TaskBooking.category == category)
        results = query.order_by(desc(TaskBooking.created_at)).limit(limit).all()
        return [item.to_dict() for item in results]


def get_task_booking_by_id(booking_id: str) -> Optional[Dict[str, Any]]:
    """Query a single booking by ID and return a Python dictionary."""
    with get_db_session() as db:
        item = db.query(TaskBooking).filter(TaskBooking.id == booking_id).first()
        return item.to_dict() if item else None


def query_latest_events(
    after_id: Optional[int] = None,
    session_id: Optional[str] = None,
    limit: int = 15,
) -> List[Dict[str, Any]]:
    """Query latest live events as a list of Python dictionaries."""
    with get_db_session() as db:
        query = db.query(LiveEventLog)
        if after_id is not None:
            query = query.filter(LiveEventLog.id > after_id)
        if session_id:
            query = query.filter(
                (LiveEventLog.session_id == session_id) | (LiveEventLog.session_id.is_(None))
            )
        events = query.order_by(LiveEventLog.id.asc()).limit(limit).all()
        return [evt.to_dict() for evt in events]


def get_system_counts() -> Dict[str, Any]:
    """Retrieve operational statistics as a Python dictionary."""
    with get_db_session() as db:
        total_tasks = db.query(TaskBooking).count()
        pending_tasks = db.query(TaskBooking).filter(TaskBooking.status == "pending").count()
        confirmed_tasks = db.query(TaskBooking).filter(TaskBooking.status == "confirmed").count()
        total_events = db.query(LiveEventLog).count()

        return {
            "total_tasks": total_tasks,
            "pending_tasks": pending_tasks,
            "confirmed_tasks": confirmed_tasks,
            "total_events_logged": total_events,
            "turso_connected": TURSO_ENABLED and TURSO_CLIENT is not None,
            "database_backend": "Turso LibSQL (Cloud) + SQLite (Local)" if TURSO_CLIENT else "SQLite (Local)",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
