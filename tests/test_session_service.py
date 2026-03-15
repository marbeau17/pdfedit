"""Tests for SessionService."""
from datetime import datetime, timedelta, UTC
from unittest.mock import patch

from app.services.session_service import SessionService


def test_create_session(sample_pdf: bytes):
    """Creating a session returns an ID and the session exists."""
    sid = SessionService.create(sample_pdf, "test.pdf")
    assert isinstance(sid, str)
    assert len(sid) == 12
    assert SessionService.exists(sid)


def test_get_pdf(sample_pdf: bytes):
    """get_pdf returns the same bytes that were stored."""
    sid = SessionService.create(sample_pdf, "test.pdf")
    retrieved = SessionService.get_pdf(sid)
    assert retrieved == sample_pdf


def test_update_and_undo(sample_pdf: bytes):
    """After update, get_pdf returns new bytes; after undo, original bytes."""
    sid = SessionService.create(sample_pdf, "test.pdf")
    new_bytes = b"%PDF-new-content"
    SessionService.update_pdf(sid, new_bytes, operation="test_op")
    assert SessionService.get_pdf(sid) == new_bytes

    success = SessionService.undo(sid)
    assert success is True
    assert SessionService.get_pdf(sid) == sample_pdf


def test_delete(sample_pdf: bytes):
    """After delete, get_pdf returns None."""
    sid = SessionService.create(sample_pdf, "test.pdf")
    SessionService.delete(sid)
    assert SessionService.get_pdf(sid) is None


def test_has_undo(sample_pdf: bytes):
    """has_undo is False initially and True after an update."""
    sid = SessionService.create(sample_pdf, "test.pdf")
    assert SessionService.has_undo(sid) is False

    SessionService.update_pdf(sid, b"%PDF-changed", operation="edit")
    assert SessionService.has_undo(sid) is True


def test_max_history(sample_pdf: bytes):
    """History length never exceeds MAX_HISTORY (10)."""
    sid = SessionService.create(sample_pdf, "test.pdf")
    for i in range(15):
        SessionService.update_pdf(sid, f"%PDF-v{i}".encode(), operation=f"op{i}")

    session = SessionService._store[sid]
    assert len(session["history"]) <= SessionService.MAX_HISTORY


def test_cleanup_expired(sample_pdf: bytes):
    """cleanup_expired removes sessions older than SESSION_TTL."""
    sid = SessionService.create(sample_pdf, "test.pdf")

    # Manually set created_at to 2 hours ago (TTL is 1 hour)
    SessionService._store[sid]["created_at"] = datetime.now(UTC) - timedelta(hours=2)

    removed = SessionService.cleanup_expired()
    assert removed == 1
    assert SessionService.get_pdf(sid) is None
