"""Tests for GeminiService (unit tests without real API calls)."""
from app.services.gemini_service import (
    create_task, get_task, cleanup_tasks, TaskStatus, AITask,
)


def test_create_task():
    """create_task returns an AITask with pending status."""
    task = create_task("test-001", "analyze")
    assert task.task_id == "test-001"
    assert task.status == TaskStatus.PENDING
    assert task.progress == 0


def test_get_task():
    """get_task retrieves a previously created task."""
    create_task("test-002", "generate")
    task = get_task("test-002")
    assert task is not None
    assert task.task_type == "generate"


def test_get_nonexistent_task():
    """get_task returns None for unknown task ID."""
    assert get_task("nonexistent") is None


def test_task_status_transitions():
    """Task status can be updated through lifecycle."""
    task = create_task("test-003", "analyze")
    assert task.status == TaskStatus.PENDING

    task.status = TaskStatus.ANALYZING
    assert task.status == TaskStatus.ANALYZING

    task.progress = 50
    task.completed_pages = 2
    task.total_pages = 4

    task.status = TaskStatus.COMPLETED
    task.progress = 100
    assert task.status == TaskStatus.COMPLETED


def test_cleanup_tasks():
    """cleanup_tasks removes excess completed tasks."""
    # This test just verifies the function runs without error
    cleanup_tasks()
