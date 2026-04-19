"""Tests for SessionManager."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from consensus_mcp.server import (LOCK_FILE, SESSIONS_FILE, SessionManager)


@pytest.fixture
def temp_session_file():
    """Create a temporary sessions file for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_sessions = Path(tmpdir) / "sessions.json"
        temp_lock = Path(tmpdir) / "sessions.lock"

        # Monkey patch the module-level constants before SessionManager initialization
        import consensus_mcp.server as server_module

        original_sessions_file = server_module.SESSIONS_FILE
        original_lock_file = server_module.LOCK_FILE

        server_module.SESSIONS_FILE = temp_sessions
        server_module.LOCK_FILE = temp_lock

        yield temp_sessions, temp_lock

        # Restore original values
        server_module.SESSIONS_FILE = original_sessions_file
        server_module.LOCK_FILE = original_lock_file


def test_create_session(temp_session_file):
    """Test session creation."""
    temp_sessions, _ = temp_session_file
    manager = SessionManager()

    agent_configs = [{"name": "TestAgent", "type": "scientist", "role": "Test role"}]

    session = manager.create_session(
        topic="Test topic",
        goals="Test goals",
        agent_configs=agent_configs,
        max_rounds=3,
    )

    assert session is not None
    assert session.topic == "Test topic"
    assert session.goals == "Test goals"
    assert session.round == 1
    assert session.max_rounds == 3
    assert len(session.agents) == 1
    assert session.phase.name == "SETUP"

    # Verify session was written to file
    assert temp_sessions.exists()
    with open(temp_sessions, "r") as f:
        data = json.load(f)
        assert len(data) == 1
        assert data[0]["topic"] == "Test topic"


def test_get_session(temp_session_file):
    """Test retrieving a session."""
    temp_sessions, _ = temp_session_file
    manager = SessionManager()

    agent_configs = [{"name": "TestAgent", "type": "scientist", "role": "Test role"}]

    session = manager.create_session(
        topic="Test topic", goals="Test goals", agent_configs=agent_configs
    )

    retrieved = manager.get_session(session.id)
    assert retrieved is not None
    assert retrieved.id == session.id
    assert retrieved.topic == session.topic


def test_get_nonexistent_session(temp_session_file):
    """Test retrieving a non-existent session."""
    _, _ = temp_session_file
    manager = SessionManager()

    retrieved = manager.get_session("nonexistent-id")
    assert retrieved is None


def test_add_contribution(temp_session_file):
    """Test adding a contribution to a session."""
    temp_sessions, _ = temp_session_file
    manager = SessionManager()

    agent_configs = [{"name": "TestAgent", "type": "scientist", "role": "Test role"}]

    session = manager.create_session(
        topic="Test topic", goals="Test goals", agent_configs=agent_configs
    )

    agent_id = list(session.agents.keys())[0]
    contribution = manager.add_contribution(
        session_id=session.id, agent_id=agent_id, content="Test contribution"
    )

    assert contribution is not None
    assert contribution.content == "Test contribution"

    # Verify contribution was written to file
    retrieved_session = manager.get_session(session.id)
    assert len(retrieved_session.contributions) == 1


def test_add_contribution_invalid_session(temp_session_file):
    """Test adding contribution to invalid session."""
    _, _ = temp_session_file
    manager = SessionManager()

    contribution = manager.add_contribution(
        session_id="nonexistent-id", agent_id="agent-id", content="Test contribution"
    )

    assert contribution is None


def test_add_agreement(temp_session_file):
    """Test adding an agreement to a session."""
    temp_sessions, _ = temp_session_file
    manager = SessionManager()

    agent_configs = [{"name": "TestAgent", "type": "scientist", "role": "Test role"}]

    session = manager.create_session(
        topic="Test topic", goals="Test goals", agent_configs=agent_configs
    )

    result = manager.add_agreement(session.id, "Test agreement")
    assert result is True

    # Verify agreement was written to file
    retrieved_session = manager.get_session(session.id)
    assert "Test agreement" in retrieved_session.agreements


def test_add_disagreement(temp_session_file):
    """Test adding a disagreement to a session."""
    temp_sessions, _ = temp_session_file
    manager = SessionManager()

    agent_configs = [{"name": "TestAgent", "type": "scientist", "role": "Test role"}]

    session = manager.create_session(
        topic="Test topic", goals="Test goals", agent_configs=agent_configs
    )

    result = manager.add_disagreement(session.id, "Test disagreement")
    assert result is True

    # Verify disagreement was written to file
    retrieved_session = manager.get_session(session.id)
    assert "Test disagreement" in retrieved_session.disagreements


def test_advance_phase(temp_session_file):
    """Test advancing session phase."""
    temp_sessions, _ = temp_session_file
    manager = SessionManager()

    agent_configs = [{"name": "TestAgent", "type": "scientist", "role": "Test role"}]

    session = manager.create_session(
        topic="Test topic", goals="Test goals", agent_configs=agent_configs
    )

    initial_phase = session.phase
    new_phase = manager.advance_phase(session.id)

    assert new_phase != initial_phase

    # Verify phase was written to file
    retrieved_session = manager.get_session(session.id)
    assert retrieved_session.phase == new_phase


def test_set_phase(temp_session_file):
    """Test setting session phase."""
    temp_sessions, _ = temp_session_file
    from consensus_mcp.server import SessionPhase

    manager = SessionManager()

    agent_configs = [{"name": "TestAgent", "type": "scientist", "role": "Test role"}]

    session = manager.create_session(
        topic="Test topic", goals="Test goals", agent_configs=agent_configs
    )

    result = manager.set_phase(session.id, SessionPhase.COMPLETE)
    assert result is True

    # Verify phase was written to file
    retrieved_session = manager.get_session(session.id)
    assert retrieved_session.phase == SessionPhase.COMPLETE


def test_list_all_sessions(temp_session_file):
    """Test listing all sessions."""
    temp_sessions, _ = temp_session_file
    manager = SessionManager()

    agent_configs = [{"name": "TestAgent", "type": "scientist", "role": "Test role"}]

    session1 = manager.create_session(
        topic="Test topic 1", goals="Test goals 1", agent_configs=agent_configs
    )
    session2 = manager.create_session(
        topic="Test topic 2", goals="Test goals 2", agent_configs=agent_configs
    )

    sessions = manager.list_all_sessions()
    assert len(sessions) == 2
    session_ids = [s.id for s in sessions]
    assert session1.id in session_ids
    assert session2.id in session_ids


def test_delete_session(temp_session_file):
    """Test deleting a session."""
    temp_sessions, _ = temp_session_file
    manager = SessionManager()

    agent_configs = [{"name": "TestAgent", "type": "scientist", "role": "Test role"}]

    session = manager.create_session(
        topic="Test topic", goals="Test goals", agent_configs=agent_configs
    )

    result = manager.delete_session(session.id)
    assert result is True

    # Verify session was deleted from file
    retrieved_session = manager.get_session(session.id)
    assert retrieved_session is None


def test_clear_all_sessions(temp_session_file):
    """Test clearing all sessions."""
    temp_sessions, _ = temp_session_file
    manager = SessionManager()

    agent_configs = [{"name": "TestAgent", "type": "scientist", "role": "Test role"}]

    manager.create_session(
        topic="Test topic 1", goals="Test goals 1", agent_configs=agent_configs
    )
    manager.create_session(
        topic="Test topic 2", goals="Test goals 2", agent_configs=agent_configs
    )

    count = manager.clear_all_sessions()
    assert count == 2

    # Verify all sessions were cleared from file
    sessions = manager.list_all_sessions()
    assert len(sessions) == 0
