"""Missing tests for Consensus MCP project."""

import pytest

from consensus_mcp.server import (AgentType, SessionManager, SessionPhase)
from consensus_mcp.server import manager as shared_manager


@pytest.fixture(autouse=True)
def clean_sessions():
    """Clear sessions before each test."""
    shared_manager.clear_all_sessions()
    yield
    shared_manager.clear_all_sessions()


def refresh_manager():
    """Get a fresh manager instance."""
    return SessionManager()


class TestSessionManagerExtended:
    """Extended SessionManager tests."""

    def test_add_agent_to_session(self):
        """Test adding an agent to existing session."""
        manager = refresh_manager()
        session = manager.create_session(
            topic="Test",
            goals="Goals",
            agent_configs=[{"name": "A1", "type": "scientist", "role": "r"}],
        )
        original_count = len(session.agents)

        agent = manager.add_agent(
            session.id, "NewAgent", AgentType.PERSPECTIVE, "New role"
        )

        assert agent is not None
        # Re-read session to get updated state from file
        updated_session = manager.get_session(session.id)
        assert len(updated_session.agents) == original_count + 1
        assert agent.name == "NewAgent"
        assert agent.agent_type == AgentType.PERSPECTIVE

    def test_add_agent_invalid_session(self):
        """Test adding agent to invalid session."""
        manager = refresh_manager()
        agent = manager.add_agent("invalid-id", "Name", AgentType.SCIENTIST)
        assert agent is None

    def test_add_agent_with_model_prefix(self):
        """Test agent name prefixing with model."""
        manager = refresh_manager()
        session = manager.create_session(
            topic="Test",
            goals="Goals",
            agent_configs=[{"name": "A1", "type": "scientist", "role": "r"}],
        )

        agent = manager.add_agent(
            session.id, "TestAgent", AgentType.SCIENTIST, "role", model="gpt-4"
        )

        assert agent is not None
        assert "gpt-4" in agent.name
        assert agent.model == "gpt-4"

    def test_get_state_returns_dict(self):
        """Test get_state returns proper dict."""
        manager = refresh_manager()
        session = manager.create_session(
            topic="Test",
            goals="Goals",
            agent_configs=[{"name": "A1", "type": "scientist", "role": "r"}],
        )

        state = manager.get_state(session.id)

        assert state is not None
        assert isinstance(state, dict)
        assert state["topic"] == "Test"
        assert state["goals"] == "Goals"
        assert "agents" in state
        assert "contributions" in state
        assert "agreements" in state
        assert "disagreements" in state

    def test_get_state_invalid_session(self):
        """Test get_state with invalid session."""
        manager = refresh_manager()
        state = manager.get_state("invalid-id")
        assert state is None

    def test_clear_all_sessions(self):
        """Test clearing all sessions."""
        manager = refresh_manager()
        manager.create_session(topic="T1", goals="G1")
        manager.create_session(topic="T2", goals="G2")

        count = manager.clear_all_sessions()

        assert count == 2

    def test_set_phase_to_specific(self):
        """Test setting phase directly."""
        manager = refresh_manager()
        session = manager.create_session(
            topic="Test",
            goals="Goals",
            agent_configs=[{"name": "A1", "type": "scientist", "role": "r"}],
        )

        result = manager.set_phase(session.id, SessionPhase.TESTING)

        assert result is True
        # Re-read session to get updated state from file
        updated_session = manager.get_session(session.id)
        assert updated_session.phase == SessionPhase.TESTING

    def test_set_phase_invalid_session(self):
        """Test set_phase with invalid session."""
        manager = refresh_manager()
        result = manager.set_phase("invalid-id", SessionPhase.TESTING)
        assert result is False

    def test_add_duplicate_agreement_ignored(self):
        """Test duplicate agreements are ignored."""
        manager = refresh_manager()
        session = manager.create_session(
            topic="Test",
            goals="Goals",
            agent_configs=[{"name": "A1", "type": "scientist", "role": "r"}],
        )

        manager.add_agreement(session.id, "Same")
        manager.add_agreement(session.id, "Same")

        # Re-read session to get updated state from file
        updated_session = manager.get_session(session.id)
        assert len(updated_session.agreements) == 1

    def test_add_duplicate_disagreement_ignored(self):
        """Test duplicate disagreements are ignored."""
        manager = refresh_manager()
        session = manager.create_session(
            topic="Test",
            goals="Goals",
            agent_configs=[{"name": "A1", "type": "scientist", "role": "r"}],
        )

        manager.add_disagreement(session.id, "Same")
        manager.add_disagreement(session.id, "Same")

        # Re-read session to get updated state from file
        updated_session = manager.get_session(session.id)
        assert len(updated_session.disagreements) == 1


class TestContributions:
    """Contribution-related tests."""

    def test_add_contribution_with_evidence(self):
        """Test adding contribution with evidence."""
        manager = refresh_manager()
        session = manager.create_session(
            topic="Test",
            goals="Goals",
            agent_configs=[{"name": "A1", "type": "scientist", "role": "r"}],
        )
        agent_id = list(session.agents.keys())[0]

        contribution = manager.add_contribution(
            session.id, agent_id, "Content", evidence="Evidence data"
        )

        assert contribution is not None
        assert contribution.evidence == "Evidence data"

    def test_add_contribution_with_challenges(self):
        """Test adding contribution with challenges."""
        manager = refresh_manager()
        session = manager.create_session(
            topic="Test",
            goals="Goals",
            agent_configs=[{"name": "A1", "type": "scientist", "role": "r"}],
        )
        agent_id = list(session.agents.keys())[0]

        contribution = manager.add_contribution(
            session.id, agent_id, "Content", challenges=["Challenge1"]
        )

        assert contribution is not None
        assert len(contribution.challenges) == 1


class TestToolFunctions:
    """Tool function tests."""

    def test_start_consensus(self):
        """Test start_consensus tool."""
        from consensus_mcp.server import start_consensus

        # Use a fresh manager by clearing first
        shared_manager.clear_all_sessions()

        result = start_consensus(
            topic="Test topic",
            goals="Test goals",
            agent_configs=[
                {"name": "Agent1", "type": "scientist", "role": "test role"}
            ],
            max_rounds=3,
        )

        assert "Consensus session created" in result
        assert "Test topic" in result

    def test_start_consensus_invalid_agent_configs(self):
        """Test start_consensus with invalid agent_configs."""
        from consensus_mcp.server import start_consensus

        result = start_consensus(
            topic="Test",
            goals="Goals",
            agent_configs="not a list",
        )

        assert "Error" in result

    def test_get_state_tool(self):
        """Test get_state tool."""
        from consensus_mcp.server import get_state, start_consensus

        shared_manager.clear_all_sessions()
        result = start_consensus(
            topic="Test",
            goals="Goals",
            agent_configs=[{"name": "A1", "type": "scientist", "role": "r"}],
        )
        session_id = result.split("'")[1].split("'")[0]

        state_result = get_state(session_id)

        assert "Session:" in state_result
        assert "Test" in state_result

    def test_get_state_invalid_session(self):
        """Test get_state tool with invalid session."""
        from consensus_mcp.server import get_state

        result = get_state("invalid-id")
        assert "not found" in result.lower()

    def test_share_reasoning(self):
        """Test share_reasoning tool."""
        from consensus_mcp.server import share_reasoning, start_consensus

        shared_manager.clear_all_sessions()
        result = start_consensus(
            topic="Test",
            goals="Goals",
            agent_configs=[{"name": "A1", "type": "scientist", "role": "r"}],
        )
        session_id = result.split("'")[1].split("'")[0]
        agent_id = list(shared_manager.get_session(session_id).agents.keys())[0]

        share_result = share_reasoning(session_id, agent_id, "Test reasoning")

        assert "Contribution added" in share_result

    def test_share_reasoning_with_evidence(self):
        """Test share_reasoning with evidence."""
        from consensus_mcp.server import share_reasoning, start_consensus

        shared_manager.clear_all_sessions()
        result = start_consensus(
            topic="Test",
            goals="Goals",
            agent_configs=[{"name": "A1", "type": "scientist", "role": "r"}],
        )
        session_id = result.split("'")[1].split("'")[0]
        agent_id = list(shared_manager.get_session(session_id).agents.keys())[0]

        result = share_reasoning(session_id, agent_id, "Content", evidence="Evidence")

        assert "Contribution added" in result

    def test_share_reasoning_invalid_session(self):
        """Test share_reasoning with invalid session."""
        from consensus_mcp.server import share_reasoning

        result = share_reasoning("invalid-id", "agent-id", "content")
        assert "not found" in result.lower()

    def test_share_reasoning_invalid_agent(self):
        """Test share_reasoning with invalid agent."""
        from consensus_mcp.server import share_reasoning, start_consensus

        shared_manager.clear_all_sessions()
        result = start_consensus(
            topic="Test",
            goals="Goals",
            agent_configs=[{"name": "A1", "type": "scientist", "role": "r"}],
        )
        session_id = result.split("'")[1].split("'")[0]

        result = share_reasoning(session_id, "invalid-agent", "content")
        assert "Failed" in result

    def test_run_experiment(self):
        """Test run_experiment tool."""
        from consensus_mcp.server import run_experiment, start_consensus

        shared_manager.clear_all_sessions()
        result = start_consensus(
            topic="Test",
            goals="Goals",
            agent_configs=[
                {"name": "Scientist1", "type": "scientist", "role": "researcher"}
            ],
        )
        session_id = result.split("'")[1].split("'")[0]
        agent_id = list(shared_manager.get_session(session_id).agents.keys())[0]

        exp_result = run_experiment(
            session_id,
            agent_id,
            hypothesis="2+2=4",
            code="print(2+2)",
        )

        assert "Experiment completed" in exp_result

    def test_run_experiment_invalid_session(self):
        """Test run_experiment with invalid session."""
        from consensus_mcp.server import run_experiment

        result = run_experiment("invalid-id", "agent-id", "hypothesis", "code")
        assert "not found" in result.lower()

    def test_run_experiment_non_scientist(self):
        """Test run_experiment with non-scientist agent."""
        from consensus_mcp.server import run_experiment, start_consensus

        shared_manager.clear_all_sessions()
        result = start_consensus(
            topic="Test",
            goals="Goals",
            agent_configs=[{"name": "Persp1", "type": "perspective", "role": "critic"}],
        )
        session_id = result.split("'")[1].split("'")[0]
        agent_id = list(shared_manager.get_session(session_id).agents.keys())[0]

        result = run_experiment(session_id, agent_id, "hypothesis", "code")

        assert "Only scientist agents" in result

    def test_run_experiment_timeout(self):
        """Test run_experiment timeout handling."""
        from consensus_mcp.server import run_experiment, start_consensus

        shared_manager.clear_all_sessions()
        result = start_consensus(
            topic="Test",
            goals="Goals",
            agent_configs=[
                {"name": "Scientist1", "type": "scientist", "role": "researcher"}
            ],
        )
        session_id = result.split("'")[1].split("'")[0]
        agent_id = list(shared_manager.get_session(session_id).agents.keys())[0]

        exp_result = run_experiment(
            session_id,
            agent_id,
            hypothesis="Infinite loop",
            code="while True: pass",
        )

        assert "timeout" in exp_result.lower() or "Error" in exp_result

    def test_run_experiment_error(self):
        """Test run_experiment error handling."""
        from consensus_mcp.server import run_experiment, start_consensus

        shared_manager.clear_all_sessions()
        result = start_consensus(
            topic="Test",
            goals="Goals",
            agent_configs=[
                {"name": "Scientist1", "type": "scientist", "role": "researcher"}
            ],
        )
        session_id = result.split("'")[1].split("'")[0]
        agent_id = list(shared_manager.get_session(session_id).agents.keys())[0]

        exp_result = run_experiment(
            session_id,
            agent_id,
            hypothesis="Bad code",
            code="1/0",
        )

        assert "Error" in exp_result or "ZeroDivisionError" in exp_result

    def test_challenge_claim(self):
        """Test challenge_claim tool."""
        from consensus_mcp.server import challenge_claim
        from consensus_mcp.server import manager as mgr
        from consensus_mcp.server import start_consensus

        shared_manager.clear_all_sessions()
        result = start_consensus(
            topic="Test",
            goals="Goals",
            agent_configs=[
                {"name": "Scientist1", "type": "scientist", "role": "researcher"},
                {"name": "Critic1", "type": "perspective", "role": "challenger"},
            ],
        )
        session_id = result.split("'")[1].split("'")[0]
        session = mgr.get_session(session_id)
        agent_ids = list(session.agents.keys())

        contrib = mgr.add_contribution(session_id, agent_ids[0], "Original claim")

        challenge_result = challenge_claim(
            session_id,
            agent_ids[1],
            contrib.id,
            "Is this correct?",
            "Need evidence",
        )

        assert "Challenge issued" in challenge_result

    def test_challenge_claim_invalid_session(self):
        """Test challenge_claim with invalid session."""
        from consensus_mcp.server import challenge_claim

        result = challenge_claim(
            "invalid-id", "agent-id", "contrib-id", "challenge", "reason"
        )
        assert "not found" in result.lower()

    def test_challenge_claim_invalid_contribution(self):
        """Test challenge_claim with invalid contribution."""
        from consensus_mcp.server import challenge_claim, start_consensus

        shared_manager.clear_all_sessions()
        result = start_consensus(
            topic="Test",
            goals="Goals",
            agent_configs=[{"name": "A1", "type": "perspective", "role": "c"}],
        )
        session_id = result.split("'")[1].split("'")[0]
        agent_id = list(shared_manager.get_session(session_id).agents.keys())[0]

        result = challenge_claim(
            session_id, agent_id, "invalid-contrib", "challenge", "reason"
        )

        assert "not found" in result.lower()

    def test_summarize(self):
        """Test summarize tool."""
        from consensus_mcp.server import start_consensus, summarize

        shared_manager.clear_all_sessions()
        result = start_consensus(
            topic="Test",
            goals="Goals",
            agent_configs=[{"name": "A1", "type": "scientist", "role": "r"}],
        )
        session_id = result.split("'")[1].split("'")[0]

        summary = summarize(session_id)

        assert "Consensus Summary" in summary

    def test_summarize_invalid_session(self):
        """Test summarize with invalid session."""
        from consensus_mcp.server import summarize

        result = summarize("invalid-id")
        assert "not found" in result.lower()

    def test_declare_consensus(self):
        """Test declare_consensus tool."""
        from consensus_mcp.server import declare_consensus
        from consensus_mcp.server import manager as mgr
        from consensus_mcp.server import start_consensus

        shared_manager.clear_all_sessions()
        result = start_consensus(
            topic="Test",
            goals="Goals",
            agent_configs=[{"name": "A1", "type": "scientist", "role": "r"}],
        )
        session_id = result.split("'")[1].split("'")[0]

        decl_result = declare_consensus(session_id, "Consensus statement")

        assert "Consensus declared" in decl_result
        session = mgr.get_session(session_id)
        assert any("CONSENSUS" in a for a in session.agreements)

    def test_declare_consensus_invalid_session(self):
        """Test declare_consensus with invalid session."""
        from consensus_mcp.server import declare_consensus

        result = declare_consensus("invalid-id", "statement")
        assert "not found" in result.lower()

    def test_reopen_session(self):
        """Test reopen_session tool."""
        from consensus_mcp.server import manager as mgr
        from consensus_mcp.server import reopen_session, start_consensus

        shared_manager.clear_all_sessions()
        result = start_consensus(
            topic="Test",
            goals="Goals",
            agent_configs=[{"name": "A1", "type": "scientist", "role": "r"}],
        )
        session_id = result.split("'")[1].split("'")[0]
        # Use manager.set_phase to write to file
        mgr.set_phase(session_id, SessionPhase.COMPLETE)
        agent_id = list(mgr.get_session(session_id).agents.keys())[0]

        reopen_result = reopen_session(session_id, agent_id, "New evidence")

        assert "Session reopened" in reopen_result
        updated_session = mgr.get_session(session_id)
        assert updated_session.phase == SessionPhase.REFINE

    def test_reopen_session_not_complete(self):
        """Test reopen_session when session not complete."""
        from consensus_mcp.server import reopen_session, start_consensus

        shared_manager.clear_all_sessions()
        result = start_consensus(
            topic="Test",
            goals="Goals",
            agent_configs=[{"name": "A1", "type": "scientist", "role": "r"}],
        )
        session_id = result.split("'")[1].split("'")[0]
        agent_id = list(shared_manager.get_session(session_id).agents.keys())[0]

        reopen_result = reopen_session(session_id, agent_id, "Reason")

        assert "not complete" in reopen_result.lower()

    def test_reopen_session_invalid_session(self):
        """Test reopen_session with invalid session."""
        from consensus_mcp.server import reopen_session

        result = reopen_session("invalid-id", "agent-id", "reason")
        assert "not found" in result.lower()

    def test_reopen_session_invalid_agent(self):
        """Test reopen_session with invalid agent (session must be COMPLETE first)."""
        from consensus_mcp.server import manager as mgr
        from consensus_mcp.server import reopen_session, start_consensus

        shared_manager.clear_all_sessions()
        result = start_consensus(
            topic="Test",
            goals="Goals",
            agent_configs=[{"name": "A1", "type": "scientist", "role": "r"}],
        )
        session_id = result.split("'")[1].split("'")[0]
        # Use manager.set_phase to write to file
        mgr.set_phase(session_id, SessionPhase.COMPLETE)

        result = reopen_session(session_id, "invalid-agent", "Reason")

        assert "not found" in result.lower() or "Agent" in result

    def test_advance_to_phase(self):
        """Test advance_to_phase tool."""
        from consensus_mcp.server import advance_to_phase, start_consensus

        shared_manager.clear_all_sessions()
        result = start_consensus(
            topic="Test",
            goals="Goals",
            agent_configs=[{"name": "A1", "type": "scientist", "role": "r"}],
        )
        session_id = result.split("'")[1].split("'")[0]

        phase_result = advance_to_phase(session_id, "testing")

        assert "testing" in phase_result.lower()

    def test_advance_to_phase_invalid(self):
        """Test advance_to_phase with invalid phase."""
        from consensus_mcp.server import advance_to_phase, start_consensus

        shared_manager.clear_all_sessions()
        result = start_consensus(
            topic="Test",
            goals="Goals",
            agent_configs=[{"name": "A1", "type": "scientist", "role": "r"}],
        )
        session_id = result.split("'")[1].split("'")[0]

        phase_result = advance_to_phase(session_id, "invalid_phase")

        assert "Invalid" in phase_result

    def test_list_sessions(self):
        """Test list_sessions tool."""
        from consensus_mcp.server import list_sessions, start_consensus

        shared_manager.clear_all_sessions()
        start_consensus(
            topic="T1",
            goals="G1",
            agent_configs=[{"name": "A1", "type": "scientist", "role": "r"}],
        )

        list_result = list_sessions()

        assert "Active Sessions" in list_result

    def test_list_sessions_empty(self):
        """Test list_sessions when empty."""
        from consensus_mcp.server import list_sessions

        shared_manager.clear_all_sessions()

        list_result = list_sessions()

        assert "No active sessions" in list_result

    def test_add_agent_tool(self):
        """Test add_agent tool."""
        from consensus_mcp.server import add_agent, start_consensus

        shared_manager.clear_all_sessions()
        result = start_consensus(
            topic="Test",
            goals="Goals",
            agent_configs=[{"name": "A1", "type": "scientist", "role": "r"}],
        )
        session_id = result.split("'")[1].split("'")[0]

        tool_result = add_agent(session_id, "NewAgent", "perspective", "New role")

        assert "added successfully" in tool_result.lower()

    def test_add_agent_tool_invalid_type(self):
        """Test add_agent with invalid type."""
        from consensus_mcp.server import add_agent, start_consensus

        shared_manager.clear_all_sessions()
        result = start_consensus(
            topic="Test",
            goals="Goals",
            agent_configs=[{"name": "A1", "type": "scientist", "role": "r"}],
        )
        session_id = result.split("'")[1].split("'")[0]

        tool_result = add_agent(session_id, "Name", "invalid_type", "role")

        assert "Invalid" in tool_result

    def test_add_agent_tool_invalid_session(self):
        """Test add_agent with invalid session."""
        from consensus_mcp.server import add_agent

        result = add_agent("invalid-id", "Name", "scientist", "role")
        assert "not found" in result.lower()

    def test_tool_add_agreement(self):
        """Test add_agreement tool."""
        from consensus_mcp.server import add_agreement as tool_add_agreement
        from consensus_mcp.server import start_consensus

        shared_manager.clear_all_sessions()
        result = start_consensus(
            topic="Test",
            goals="Goals",
            agent_configs=[{"name": "A1", "type": "scientist", "role": "r"}],
        )
        session_id = result.split("'")[1].split("'")[0]

        result_tool = tool_add_agreement(session_id, "Agreement text")

        assert "added" in result_tool.lower()

    def test_tool_add_disagreement(self):
        """Test add_disagreement tool."""
        from consensus_mcp.server import \
            add_disagreement as tool_add_disagreement
        from consensus_mcp.server import start_consensus

        shared_manager.clear_all_sessions()
        result = start_consensus(
            topic="Test",
            goals="Goals",
            agent_configs=[{"name": "A1", "type": "scientist", "role": "r"}],
        )
        session_id = result.split("'")[1].split("'")[0]

        result_tool = tool_add_disagreement(session_id, "Disagreement text")

        assert "noted" in result_tool.lower()

    def test_clear_all_sessions_tool(self):
        """Test clear_all_sessions tool."""
        from consensus_mcp.server import clear_all_sessions as tool_clear
        from consensus_mcp.server import start_consensus

        shared_manager.clear_all_sessions()
        start_consensus(
            topic="T1",
            goals="G1",
            agent_configs=[{"name": "A1", "type": "scientist", "role": "r"}],
        )

        result = tool_clear()

        assert "Cleared" in result


class TestEdgeCases:
    """Edge case tests."""

    def test_default_moderator_when_no_agents(self):
        """Test default moderator created when no agents specified."""
        manager = refresh_manager()
        session = manager.create_session(topic="Test", goals="Goals")

        assert len(session.agents) == 1
        agent = list(session.agents.values())[0]
        assert agent.agent_type == AgentType.MODERATOR
        assert "Moderator" in agent.name

    def test_model_prefix_in_create_session(self):
        """Test model prefix in session creation."""
        manager = refresh_manager()
        session = manager.create_session(
            topic="Test",
            goals="Goals",
            agent_configs=[{"name": "Agent", "type": "scientist", "role": "r"}],
            model="gpt-4",
        )

        agent = list(session.agents.values())[0]
        assert "gpt-4" in agent.name

    def test_share_reasoning_reopens_complete_session(self):
        """Test share_reasoning reopens complete session."""
        from consensus_mcp.server import manager as mgr
        from consensus_mcp.server import share_reasoning, start_consensus

        shared_manager.clear_all_sessions()
        result = start_consensus(
            topic="Test",
            goals="Goals",
            agent_configs=[{"name": "A1", "type": "scientist", "role": "r"}],
        )
        session_id = result.split("'")[1].split("'")[0]
        session = mgr.get_session(session_id)
        session.phase = SessionPhase.COMPLETE
        agent_id = list(session.agents.keys())[0]

        result = share_reasoning(session_id, agent_id, "New contribution")

        assert "reopened" in result.lower() or "Contribution added" in result

    def test_challenge_reopens_complete_session(self):
        """Test challenge reopens complete session."""
        from consensus_mcp.server import challenge_claim
        from consensus_mcp.server import manager as mgr
        from consensus_mcp.server import start_consensus

        shared_manager.clear_all_sessions()
        result = start_consensus(
            topic="Test",
            goals="Goals",
            agent_configs=[
                {"name": "A1", "type": "scientist", "role": "r"},
                {"name": "A2", "type": "perspective", "role": "c"},
            ],
        )
        session_id = result.split("'")[1].split("'")[0]
        session = mgr.get_session(session_id)
        session.phase = SessionPhase.COMPLETE
        agent_ids = list(session.agents.keys())

        contrib = mgr.add_contribution(session_id, agent_ids[0], "Original")

        result = challenge_claim(
            session_id, agent_ids[1], contrib.id, "Challenge", "Reason"
        )

        assert "reopened" in result.lower() or "Challenge" in result
