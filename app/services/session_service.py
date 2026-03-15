"""PDF Session Management Service.

Manages uploaded PDFs in memory with session IDs, TTL expiry, and undo history.
"""
from datetime import datetime, timedelta, UTC
import uuid


class SessionService:
    """In-memory PDF session store with undo support."""

    _store: dict[str, dict] = {}
    SESSION_TTL = timedelta(hours=1)
    MAX_HISTORY = 10

    @classmethod
    def create(cls, pdf_bytes: bytes, filename: str) -> str:
        """Create a new session and return session_id."""
        session_id = uuid.uuid4().hex[:12]
        cls._store[session_id] = {
            "pdf_bytes": pdf_bytes,
            "original_filename": filename,
            "created_at": datetime.now(UTC),
            "history": [],
        }
        return session_id

    @classmethod
    def get_pdf(cls, session_id: str) -> bytes | None:
        """Get PDF bytes for a session, or None if expired/missing."""
        session = cls._store.get(session_id)
        if not session:
            return None
        if datetime.now(UTC) - session["created_at"] > cls.SESSION_TTL:
            cls.delete(session_id)
            return None
        return session["pdf_bytes"]

    @classmethod
    def get_filename(cls, session_id: str) -> str:
        """Get original filename for a session."""
        session = cls._store.get(session_id)
        if session:
            return session["original_filename"]
        return "document.pdf"

    @classmethod
    def update_pdf(cls, session_id: str, new_bytes: bytes, operation: str = ""):
        """Update PDF bytes, saving current state to history for undo."""
        session = cls._store.get(session_id)
        if session:
            session["history"].append(session["pdf_bytes"])
            if len(session["history"]) > cls.MAX_HISTORY:
                session["history"].pop(0)
            session["pdf_bytes"] = new_bytes

    @classmethod
    def undo(cls, session_id: str) -> bool:
        """Undo last operation. Returns True if successful."""
        session = cls._store.get(session_id)
        if session and session["history"]:
            session["pdf_bytes"] = session["history"].pop()
            return True
        return False

    @classmethod
    def has_undo(cls, session_id: str) -> bool:
        """Check if undo is available."""
        session = cls._store.get(session_id)
        return bool(session and session["history"])

    @classmethod
    def delete(cls, session_id: str):
        """Delete a session."""
        cls._store.pop(session_id, None)

    @classmethod
    def exists(cls, session_id: str) -> bool:
        """Check if session exists and is not expired."""
        return cls.get_pdf(session_id) is not None

    @classmethod
    def cleanup_expired(cls):
        """Remove all expired sessions."""
        now = datetime.now(UTC)
        expired = [
            sid for sid, data in cls._store.items()
            if now - data["created_at"] > cls.SESSION_TTL
        ]
        for sid in expired:
            cls._store.pop(sid, None)
        return len(expired)

    @classmethod
    def active_count(cls) -> int:
        """Return number of active sessions."""
        return len(cls._store)
