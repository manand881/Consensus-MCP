"""Consensus MCP server implementation."""

import fcntl
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import markdown

from fastmcp import FastMCP
from jinja2 import Environment, FileSystemLoader
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse

# Configure logging
log_file = Path(__file__).parent / "consensus_server.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Session storage file
SESSIONS_FILE = Path(__file__).parent / "sessions.json"

# File lock for concurrent access
LOCK_FILE = Path(__file__).parent / "sessions.lock"

mcp = FastMCP(
    "Consensus MCP",
    instructions=(
        "Enables multiple AI agents to reason together, challenge assumptions, run experiments, "
        "and converge on truth through structured dialogue.\n"
        "## Markdown Support\n"
        "**IMPORTANT**: This server supports Markdown formatting for all text submissions. When contributing content, "
        "you should use Markdown to make your responses more readable and structured. Markdown will be rendered "
        "nicely in the web UI. Use formatting like:\n"
        "- **Bold** and *italic* text for emphasis\n"
        "- `code` or ```code blocks``` for technical content\n"
        "- # Headers for organization\n"
        "- - Bullet points for lists\n"
        "- > Blockquotes for highlighting important points\n"
        "- Tables for structured data\n"
        "**CRITICAL**: Avoid using double newlines (\\n\\n) excessively. Use single newlines between sentences within a paragraph. "
        "Only use double newlines to separate distinct paragraphs or sections. Excessive spacing makes content look ugly and hard to read.\n"
        "## Agent Types\n"
        "When creating a consensus session, choose agents based on the topic. There are 6 agent types:\n"
        "1. **scientist** - Tests hypotheses through code execution and experiments. Responsibilities: "
        "propose falsifiable hypotheses, write and execute test code, share experimental results objectively, "
        "validate or refute claims via evidence. Only scientist agents can use the `run_experiment` tool.\n"
        "2. **perspective** - Provides domain expertise and challenges assumptions from different angles. "
        "Responsibilities: offer alternative viewpoints, challenge reasoning gaps, build on others' arguments, "
        "identify blind spots and edge cases. Create multiple perspective agents with different expertise/roles "
        "to represent different sides of a debate.\n"
        "3. **synthesizer** - Tracks convergence and identifies consensus points. Responsibilities: "
        "identify areas of agreement, highlight unresolved disagreements, summarize shared understanding, "
        "detect when consensus is reached. Typically 1 synthesizer per session.\n"
        "4. **moderator** - Manages the consensus flow and enforces structure. Responsibilities: "
        "introduce topic and goals, manage turn-taking, prompt agents for evidence/challenges, "
        "control session phases. Exactly 1 moderator per session.\n"
        "5. **bug_hunter** - Automatically spawned when session enters implementing phase. Responsibilities: "
        "analyze changed files for bugs, report bugs with details (file, description, severity, line number), "
        "work with code verification agent to ensure code quality. One bug hunter is spawned per existing agent.\n"
        "6. **code_verification** - Automatically spawned when session enters implementing phase. Responsibilities: "
        "verify bug reports from bug hunter agents, validate or reject bug findings, provide verification comments, "
        "ensure only legitimate bugs are addressed. Exactly 1 code verification agent per session.\n"
        "## Recommended Agent Composition\n"
        "- Always include exactly 1 **moderator** to manage the session flow.\n"
        "- Include at least 1 **scientist** if the topic involves testable/falsifiable claims.\n"
        "- Include 2+ **perspective** agents with opposing or complementary expertise to ensure debate. "
        "Each should have a descriptive `role` reflecting their specific viewpoint.\n"
        "- Include exactly 1 **synthesizer** to track convergence.\n"
        "- Typical session: 1 moderator + 1 scientist + 2-3 perspectives + 1 synthesizer = 5-6 agents.\n"
        "## Consensus Flow\n"
        "Sessions progress through phases: clarification -> setup -> position -> testing -> challenge -> synthesis -> refine -> convergence -> implementing -> complete.\n"
        "- **clarification**: LLM asks user clarifying questions about topic/goals before debate starts. User answers via chat or web UI.\n"
        "- **setup**: Moderator introduces topic, goals, and rules.\n"
        "- **position**: Agents share initial reasoning and evidence.\n"
        "- **testing**: Scientist agents run experiments, share results.\n"
        "- **challenge**: Perspective agents question and counter.\n"
        "- **synthesis**: Synthesizer identifies agreement/disagreement.\n"
        "- **refine**: Agents address gaps, update positions.\n"
        "- **convergence**: Repeat until consensus or max rounds.\n"
        "- **implementing**: Consensus reached, implementation of the agreed-upon solution begins.\n"
        "- **complete**: Final consensus statement with reasoning.\n"
        "## Orchestration Guide\n"
        "The MCP server provides tools but does NOT auto-invoke agents. External orchestrators must:\n"
        "### Phase-by-Phase Agent Calling Sequence:\n"
        "- **clarification phase**: Use ask_question to ask user clarifying questions about topic/goals. Wait for user to answer via submit_answer or web UI. Once clarification is complete, use advance_phase to move to setup.\n"
        "- **setup phase**: Call moderator to introduce topic and set goals\n"
        "- **position phase**: Call all perspective agents to share initial views (use share_reasoning)\n"
        "- **testing phase**: Call scientist to run experiments (use run_experiment)\n"
        "- **challenge phase**: Call perspective agents to dispute claims (use challenge_claim)\n"
        "- **synthesis phase**: Call synthesizer to analyze convergence (use summarize, add_agreement, add_disagreement)\n"
        "- **refine phase**: Call agents to address gaps (use share_reasoning)\n"
        "- **convergence phase**: Call synthesizer to declare consensus (use declare_consensus)\n"
        "- **implementing phase**: Implementation of the agreed-upon solution begins\n"
        "- **complete phase**: Session ends\n"
        "### Moderator Responsibilities:\n"
        "- Should be called AFTER each phase to manage transitions\n"
        "- Use prompt_agent tool to direct specific agents to contribute\n"
        "- Use advance_phase tool to move to next phase\n"
        "- Detect stalemates and request evidence from scientist\n"
        "- Ensure all agents have opportunity to contribute\n"
        "### Key Orchestration Patterns:\n"
        "- After scientist provides evidence: Call synthesizer to analyze\n"
        "- After disagreement emerges: Call moderator to resolve or direct challenge\n"
        "- When consensus reached: Call synthesizer to declare_consensus\n"
        "- Use get_next_actions tool to get phase-specific guidance\n"
        "### Available Tools for Orchestration:\n"
        "- ask_question(session_id, question): Ask the user a clarifying question before debate starts\n"
        "- submit_answer(session_id, question_id, answer): Submit user's answer to a question\n"
        "- get_next_actions(session_id): Get recommended next actions based on current phase\n"
        "- prompt_agent(session_id, agent_id, instruction): Prompt a specific agent to contribute\n"
        "- advance_phase(session_id, phase): Manually advance to a specific phase\n"
    ),
)

# Set up Jinja2 template environment
template_dir = Path(__file__).parent / "templates"
env = Environment(loader=FileSystemLoader(template_dir))


def markdown_filter(text: str) -> str:
    """Convert markdown text to HTML.

    Args:
        text: Markdown formatted text

    Returns:
        HTML string
    """
    if not text:
        return ""
    # Collapse excessive newlines (more than 2 consecutive newlines to exactly 2)
    import re
    text = re.sub(r'\n{3,}', '\n', text)
    return markdown.markdown(text, extensions=["fenced_code", "tables", "nl2br"])


env.filters["markdown"] = markdown_filter


class AgentType(Enum):
    SCIENTIST = "scientist"
    PERSPECTIVE = "perspective"
    SYNTHESIZER = "synthesizer"
    MODERATOR = "moderator"
    BUG_HUNTER = "bug_hunter"
    CODE_VERIFICATION = "code_verification"


class SessionPhase(Enum):
    CLARIFICATION = "clarification"
    SETUP = "setup"
    POSITION = "position"
    TESTING = "testing"
    CHALLENGE = "challenge"
    SYNTHESIS = "synthesis"
    REFINE = "refine"
    CONVERGENCE = "convergence"
    IMPLEMENTING = "implementing"
    COMPLETE = "complete"


@dataclass
class Agent:
    id: str
    name: str
    agent_type: AgentType
    role: str
    model: str = "default"


@dataclass
class Contribution:
    id: str
    agent_id: str
    agent_name: str
    agent_type: AgentType
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    evidence: str | None = None
    challenges: list[str] = field(default_factory=list)


@dataclass
class Question:
    id: str
    question: str
    timestamp: datetime = field(default_factory=datetime.now)
    answer: str | None = None


@dataclass
class ConsensusSession:
    id: str
    topic: str
    goals: str
    phase: SessionPhase
    round: int
    max_rounds: int
    agents: dict[str, Agent] = field(default_factory=dict)
    contributions: list[Contribution] = field(default_factory=list)
    agreements: list[str] = field(default_factory=list)
    disagreements: list[str] = field(default_factory=list)
    questions: list[Question] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    bugs: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


class SessionManager:
    def __init__(self):
        """Initialize SessionManager with file-only storage.

        No in-memory storage - all data read/written from file.
        """
        self._ensure_sessions_file_exists()

    def _ensure_sessions_file_exists(self):
        """Ensure sessions.json file exists."""
        if not SESSIONS_FILE.exists():
            SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(SESSIONS_FILE, "w") as f:
                json.dump([], f)

    def _acquire_lock(self):
        """Acquire file lock for concurrent access."""
        lock_fd = open(LOCK_FILE, "w")
        try:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
        except (AttributeError, IOError):
            # fcntl not available on Windows, use simple file-based lock
            pass
        return lock_fd

    def _release_lock(self, lock_fd):
        """Release file lock."""
        try:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
        except (AttributeError, IOError):
            pass
        lock_fd.close()

    def _read_sessions(self) -> dict[str, ConsensusSession]:
        """Read all sessions from file and return as dict.

        Returns:
            Dictionary mapping session IDs to ConsensusSession objects.
            Returns empty dict if file cannot be read.
        """
        try:
            with open(SESSIONS_FILE, "r") as f:
                data = json.load(f)
                sessions = {}
                for session_data in data:
                    session = self._deserialize_session(session_data)
                    sessions[session.id] = session
                return sessions
        except Exception as e:
            logger.warning(f"Failed to read sessions: {e}")
            return {}

    def _write_sessions(self, sessions: dict[str, ConsensusSession]):
        """Write all sessions to file.

        Args:
            sessions: Dictionary mapping session IDs to ConsensusSession objects.
        """
        try:
            data = []
            for session in sessions.values():
                session_data = self._serialize_session(session)
                data.append(session_data)
            with open(SESSIONS_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to write sessions: {e}")

    def _deserialize_session(self, session_data: dict[str, Any]) -> ConsensusSession:
        """Deserialize session data from JSON dict.

        Args:
            session_data: Dictionary containing session data from JSON file.

        Returns:
            ConsensusSession object.
        """
        return ConsensusSession(
            id=session_data["id"],
            topic=session_data["topic"],
            goals=session_data["goals"],
            phase=SessionPhase(session_data["phase"]),
            round=session_data["round"],
            max_rounds=session_data["max_rounds"],
            agents={
                aid: Agent(
                    id=a["id"],
                    name=a["name"],
                    agent_type=AgentType(a["agent_type"]),
                    role=a["role"],
                    model=a.get("model", "default"),
                )
                for aid, a in session_data["agents"].items()
            },
            contributions=[
                Contribution(
                    id=c["id"],
                    agent_id=c["agent_id"],
                    agent_name=c["agent_name"],
                    agent_type=AgentType(c["agent_type"]),
                    content=c["content"],
                    timestamp=datetime.fromisoformat(c["timestamp"]),
                    evidence=c.get("evidence"),
                    challenges=c.get("challenges", []),
                )
                for c in session_data["contributions"]
            ],
            agreements=session_data.get("agreements", []),
            disagreements=session_data.get("disagreements", []),
            questions=[
                Question(
                    id=q["id"],
                    question=q["question"],
                    timestamp=datetime.fromisoformat(q["timestamp"]),
                    answer=q.get("answer"),
                )
                for q in session_data.get("questions", [])
            ],
            changed_files=session_data.get("changed_files", []),
            bugs=session_data.get("bugs", []),
            created_at=datetime.fromisoformat(session_data["created_at"]),
        )

    def _serialize_session(self, session: ConsensusSession) -> dict[str, Any]:
        """Serialize session to JSON dict.

        Args:
            session: ConsensusSession object to serialize.

        Returns:
            Dictionary suitable for JSON serialization.
        """
        return {
            "id": session.id,
            "topic": session.topic,
            "goals": session.goals,
            "phase": session.phase.value,
            "round": session.round,
            "max_rounds": session.max_rounds,
            "agents": {
                aid: {
                    "id": a.id,
                    "name": a.name,
                    "agent_type": a.agent_type.value,
                    "role": a.role,
                    "model": a.model,
                }
                for aid, a in session.agents.items()
            },
            "contributions": [
                {
                    "id": c.id,
                    "agent_id": c.agent_id,
                    "agent_name": c.agent_name,
                    "agent_type": c.agent_type.value,
                    "content": c.content,
                    "timestamp": c.timestamp.isoformat(),
                    "evidence": c.evidence,
                    "challenges": c.challenges,
                }
                for c in session.contributions
            ],
            "agreements": session.agreements,
            "disagreements": session.disagreements,
            "questions": [
                {
                    "id": q.id,
                    "question": q.question,
                    "timestamp": q.timestamp.isoformat(),
                    "answer": q.answer,
                }
                for q in session.questions
            ],
            "changed_files": session.changed_files,
            "bugs": session.bugs,
            "created_at": session.created_at.isoformat(),
        }

    def create_session(
        self,
        topic: str,
        goals: str,
        agent_configs: list[dict[str, Any]] | None = None,
        max_rounds: int = 5,
        model: str = "default",
    ) -> ConsensusSession:
        logger.info(f"Creating new consensus session: {topic}")
        lock = self._acquire_lock()
        try:
            sessions = self._read_sessions()
            session_id = str(uuid.uuid4())
            agents = {}

            # If no agents specified, create a default moderator
            if not agent_configs:
                agent_configs = [
                    {
                        "name": "Moderator",
                        "type": "moderator",
                        "role": "Session moderator - manages flow and enforces structure",
                    }
                ]

            for config in agent_configs:
                agent_id = str(uuid.uuid4())
                # Prefix agent name with model if provided
                agent_name = config["name"]
                if model and model != "default":
                    agent_name = f"{model}-{config['name']}"
                agents[agent_id] = Agent(
                    id=agent_id,
                    name=agent_name,
                    agent_type=AgentType(config["type"]),
                    role=config.get("role", ""),
                    model=model,
                )
            session = ConsensusSession(
                id=session_id,
                topic=topic,
                goals=goals,
                phase=SessionPhase.CLARIFICATION,
                round=1,
                max_rounds=max_rounds,
                agents=agents,
            )
            sessions[session_id] = session
            self._write_sessions(sessions)
            logger.info(f"Session created with ID: {session_id}, {len(agents)} agents")
            return session
        finally:
            self._release_lock(lock)

    def get_session(self, session_id: str) -> ConsensusSession | None:
        lock = self._acquire_lock()
        try:
            sessions = self._read_sessions()
            return sessions.get(session_id)
        finally:
            self._release_lock(lock)

    def add_agent(
        self,
        session_id: str,
        name: str,
        agent_type: AgentType,
        role: str = "",
        model: str = "default",
    ) -> Agent | None:
        """Add a new agent to an existing session.

        Args:
            session_id: The session ID to add the agent to
            name: The agent's name
            agent_type: The type of agent (scientist/perspective/synthesizer/moderator)
            role: The agent's role description
            model: The LLM model name to prefix

        Returns:
            The created Agent, or None if session not found
        """
        lock = self._acquire_lock()
        try:
            sessions = self._read_sessions()
            session = sessions.get(session_id)
            if not session:
                logger.warning(f"Session not found: {session_id}")
                return None

            agent_id = str(uuid.uuid4())
            # Prefix agent name with model if provided
            agent_name = name
            if model and model != "default":
                agent_name = f"{model}-{name}"

            agent = Agent(
                id=agent_id,
                name=agent_name,
                agent_type=agent_type,
                role=role,
                model=model,
            )
            session.agents[agent_id] = agent
            self._write_sessions(sessions)
            logger.info(f"Agent {agent_name} added to session {session_id}")
            return agent
        finally:
            self._release_lock(lock)

    def add_contribution(
        self,
        session_id: str,
        agent_id: str,
        content: str,
        evidence: str | None = None,
        challenges: list[str] | None = None,
    ) -> Contribution | None:
        lock = self._acquire_lock()
        try:
            sessions = self._read_sessions()
            session = sessions.get(session_id)
            if not session:
                logger.warning(f"Session not found: {session_id}")
                return None
            agent = session.agents.get(agent_id)
            if not agent:
                logger.warning(f"Agent not found: {agent_id} in session {session_id}")
                return None
            contribution = Contribution(
                id=str(uuid.uuid4()),
                agent_id=agent_id,
                agent_name=agent.name,
                agent_type=agent.agent_type,
                content=content,
                evidence=evidence,
                challenges=challenges or [],
            )
            session.contributions.append(contribution)
            self._write_sessions(sessions)
            logger.info(f"Contribution added by {agent.name} in session {session_id}")
            return contribution
        finally:
            self._release_lock(lock)

    def advance_phase(self, session_id: str) -> SessionPhase | None:
        lock = self._acquire_lock()
        try:
            sessions = self._read_sessions()
            session = sessions.get(session_id)
            if not session:
                return None
            phase_order = [
                SessionPhase.CLARIFICATION,
                SessionPhase.SETUP,
                SessionPhase.POSITION,
                SessionPhase.TESTING,
                SessionPhase.CHALLENGE,
                SessionPhase.SYNTHESIS,
                SessionPhase.REFINE,
                SessionPhase.CONVERGENCE,
                SessionPhase.IMPLEMENTING,
                SessionPhase.COMPLETE,
            ]
            try:
                current_idx = phase_order.index(session.phase)
                if current_idx < len(phase_order) - 1:
                    new_phase = phase_order[current_idx + 1]
                    session.phase = new_phase
                    if session.phase == SessionPhase.REFINE:
                        session.round += 1
                    if session.phase == SessionPhase.IMPLEMENTING:
                        self._spawn_bug_hunter_agents(session)
            except ValueError:
                pass
            self._write_sessions(sessions)
            return session.phase
        finally:
            self._release_lock(lock)

    def _spawn_bug_hunter_agents(self, session: ConsensusSession) -> None:
        """Spawn bug hunter agents for each existing agent when entering implementing phase.

        Args:
            session: The consensus session to add bug hunter agents to.
        """
        for agent in list(session.agents.values()):
            if agent.agent_type not in [AgentType.BUG_HUNTER, AgentType.CODE_VERIFICATION]:
                bug_hunter_id = str(uuid.uuid4())
                bug_hunter = Agent(
                    id=bug_hunter_id,
                    name=f"{agent.name}-BugHunter",
                    agent_type=AgentType.BUG_HUNTER,
                    role=f"Bug hunter for {agent.name} - analyzes changed files for bugs",
                    model=agent.model,
                )
                session.agents[bug_hunter_id] = bug_hunter
        # Add one code verification agent
        code_verifier_id = str(uuid.uuid4())
        code_verifier = Agent(
            id=code_verifier_id,
            name="CodeVerifier",
            agent_type=AgentType.CODE_VERIFICATION,
            role="Verifies bug reports from bug hunter agents",
            model="default",
        )
        session.agents[code_verifier_id] = code_verifier
        logger.info(f"Spawned bug hunter agents and code verifier for session {session.id}")

    def set_phase(self, session_id: str, phase: SessionPhase) -> bool:
        lock = self._acquire_lock()
        try:
            sessions = self._read_sessions()
            session = sessions.get(session_id)
            if not session:
                return False
            session.phase = phase
            if phase == SessionPhase.IMPLEMENTING:
                self._spawn_bug_hunter_agents(session)
            self._write_sessions(sessions)
            return True
        finally:
            self._release_lock(lock)

    def add_agreement(self, session_id: str, agreement: str) -> bool:
        lock = self._acquire_lock()
        try:
            sessions = self._read_sessions()
            session = sessions.get(session_id)
            if not session:
                return False
            if agreement not in session.agreements:
                session.agreements.append(agreement)
            self._write_sessions(sessions)
            return True
        finally:
            self._release_lock(lock)

    def add_disagreement(self, session_id: str, disagreement: str) -> bool:
        lock = self._acquire_lock()
        try:
            sessions = self._read_sessions()
            session = sessions.get(session_id)
            if not session:
                return False
            if disagreement not in session.disagreements:
                session.disagreements.append(disagreement)
            self._write_sessions(sessions)
            return True
        finally:
            self._release_lock(lock)

    def update_goals(self, session_id: str, goals: str) -> bool:
        """Update the goals of a session.

        Args:
            session_id: The ID of the session to update
            goals: The new goals text

        Returns:
            True if successful, False if session not found
        """
        lock = self._acquire_lock()
        try:
            sessions = self._read_sessions()
            session = sessions.get(session_id)
            if not session:
                return False
            session.goals = goals
            self._write_sessions(sessions)
            logger.info(f"Goals updated for session {session_id}")
            return True
        finally:
            self._release_lock(lock)

    def ask_question(self, session_id: str, question: str) -> Question | None:
        """Ask a question to the user in the clarification phase.

        Args:
            session_id: The ID of the session
            question: The question to ask

        Returns:
            The created Question, or None if session not found
        """
        lock = self._acquire_lock()
        try:
            sessions = self._read_sessions()
            session = sessions.get(session_id)
            if not session:
                logger.warning(f"Session not found: {session_id}")
                return None

            question_obj = Question(
                id=str(uuid.uuid4()),
                question=question,
            )
            session.questions.append(question_obj)
            self._write_sessions(sessions)
            logger.info(f"Question added to session {session_id}: {question[:50]}...")
            return question_obj
        finally:
            self._release_lock(lock)

    def submit_answer(self, session_id: str, question_id: str, answer: str) -> bool:
        """Submit an answer to a question.

        Args:
            session_id: The ID of the session
            question_id: The ID of the question to answer
            answer: The answer text

        Returns:
            True if successful, False if session or question not found
        """
        lock = self._acquire_lock()
        try:
            sessions = self._read_sessions()
            session = sessions.get(session_id)
            if not session:
                logger.warning(f"Session not found: {session_id}")
                return False

            for question in session.questions:
                if question.id == question_id:
                    question.answer = answer
                    self._write_sessions(sessions)
                    logger.info(f"Answer submitted for question {question_id} in session {session_id}")
                    return True

            logger.warning(f"Question not found: {question_id} in session {session_id}")
            return False
        finally:
            self._release_lock(lock)

    def clear_all_sessions(self) -> int:
        """Clear all sessions from storage."""
        lock = self._acquire_lock()
        try:
            sessions = self._read_sessions()
            count = len(sessions)
            sessions.clear()
            self._write_sessions(sessions)
            logger.info(f"Cleared {count} sessions")
            return count
        finally:
            self._release_lock(lock)

    def delete_session(self, session_id: str) -> bool:
        """Delete a specific session from storage.

        Args:
            session_id: The ID of the session to delete

        Returns:
            True if session was deleted, False if not found
        """
        lock = self._acquire_lock()
        try:
            sessions = self._read_sessions()
            if session_id in sessions:
                del sessions[session_id]
                self._write_sessions(sessions)
                logger.info(f"Deleted session: {session_id}")
                return True
            return False
        finally:
            self._release_lock(lock)

    def get_state(self, session_id: str) -> dict[str, Any] | None:
        lock = self._acquire_lock()
        try:
            sessions = self._read_sessions()
            session = sessions.get(session_id)
            if not session:
                return None
            return {
                "id": session.id,
                "topic": session.topic,
                "goals": session.goals,
                "phase": session.phase.value,
                "round": session.round,
                "max_rounds": session.max_rounds,
                "agents": [
                    {
                        "id": a.id,
                        "name": a.name,
                        "type": a.agent_type.value,
                        "role": a.role,
                        "model": a.model,
                    }
                    for a in session.agents.values()
                ],
                "contributions": [
                    {
                        "id": c.id,
                        "agent_name": c.agent_name,
                        "agent_type": c.agent_type.value,
                        "content": c.content,
                        "timestamp": c.timestamp.isoformat(),
                        "evidence": c.evidence,
                        "challenges": c.challenges,
                    }
                    for c in session.contributions
                ],
                "agreements": session.agreements,
                "disagreements": session.disagreements,
                "questions": [
                    {
                        "id": q.id,
                        "question": q.question,
                        "timestamp": q.timestamp.isoformat(),
                        "answer": q.answer,
                    }
                    for q in session.questions
                ],
                "created_at": session.created_at.isoformat(),
            }
        finally:
            self._release_lock(lock)

    def list_all_sessions(self) -> list[ConsensusSession]:
        """List all sessions from storage."""
        lock = self._acquire_lock()
        try:
            sessions = self._read_sessions()
            return list(sessions.values())
        finally:
            self._release_lock(lock)

    def report_bug(self, session_id: str, agent_id: str, bug_report: dict[str, Any]) -> bool:
        """Report a bug from a bug hunter agent.

        Args:
            session_id: The ID of the session
            agent_id: The ID of the bug hunter agent reporting the bug
            bug_report: Dictionary containing bug details (file, description, severity, etc.)

        Returns:
            True if successful, False if session or agent not found
        """
        lock = self._acquire_lock()
        try:
            sessions = self._read_sessions()
            session = sessions.get(session_id)
            if not session:
                logger.warning(f"Session not found: {session_id}")
                return False
            agent = session.agents.get(agent_id)
            if not agent:
                logger.warning(f"Agent not found: {agent_id} in session {session_id}")
                return False
            if agent.agent_type != AgentType.BUG_HUNTER:
                logger.warning(f"Agent {agent_id} is not a bug hunter agent")
                return False
            bug_report["reporter_id"] = agent_id
            bug_report["reporter_name"] = agent.name
            bug_report["timestamp"] = datetime.now().isoformat()
            bug_report["verified"] = False
            session.bugs.append(bug_report)
            self._write_sessions(sessions)
            logger.info(f"Bug reported by {agent.name} in session {session_id}")
            return True
        finally:
            self._release_lock(lock)

    def verify_bug(self, session_id: str, agent_id: str, bug_index: int, verified: bool, comment: str = "") -> bool:
        """Verify a bug report from a code verification agent.

        Args:
            session_id: The ID of the session
            agent_id: The ID of the code verification agent
            bug_index: The index of the bug in the bugs list
            verified: Whether the bug is verified as valid
            comment: Optional comment from the verifier

        Returns:
            True if successful, False if session, agent, or bug not found
        """
        lock = self._acquire_lock()
        try:
            sessions = self._read_sessions()
            session = sessions.get(session_id)
            if not session:
                logger.warning(f"Session not found: {session_id}")
                return False
            agent = session.agents.get(agent_id)
            if not agent:
                logger.warning(f"Agent not found: {agent_id} in session {session_id}")
                return False
            if agent.agent_type != AgentType.CODE_VERIFICATION:
                logger.warning(f"Agent {agent_id} is not a code verification agent")
                return False
            if bug_index < 0 or bug_index >= len(session.bugs):
                logger.warning(f"Bug index {bug_index} out of range in session {session_id}")
                return False
            session.bugs[bug_index]["verified"] = verified
            session.bugs[bug_index]["verified_by"] = agent_id
            session.bugs[bug_index]["verifier_name"] = agent.name
            session.bugs[bug_index]["verification_comment"] = comment
            session.bugs[bug_index]["verification_timestamp"] = datetime.now().isoformat()
            self._write_sessions(sessions)
            logger.info(f"Bug {bug_index} verified by {agent.name} in session {session_id}: {verified}")
            return True
        finally:
            self._release_lock(lock)


manager = SessionManager()


@mcp.tool
def start_consensus(
    topic: str,
    goals: str,
    agent_configs: list[dict[str, Any]],
    max_rounds: int = 5,
    model: str = "default",
) -> str:
    """Initialize a new consensus session.

    Args:
        topic: The topic or question to reach consensus on
        goals: Goals for the consensus session
        agent_configs: List of agent configurations, each with name, type, and optional role.
            Each config is a dict with keys: 'name' (str), 'type' (str), 'role' (str, optional).

            Agent types and when to use them:
            - 'moderator': Manages session flow and enforces structure. Exactly 1 per session.
            - 'scientist': Tests hypotheses through code execution and experiments. Only scientists
              can use run_experiment. Include 1+ if the topic involves testable/falsifiable claims.
            - 'perspective': Provides domain expertise and challenges assumptions. Include 2+ with
              opposing or complementary viewpoints. Each should have a descriptive 'role' reflecting
              their specific expertise (e.g., "Rails geospatial expert" vs "Django geospatial expert").
            - 'synthesizer': Tracks convergence and identifies agreement/disagreement. Exactly 1 per session.

            Recommended composition: 1 moderator + 1 scientist + 2-3 perspectives + 1 synthesizer = 5-6 agents.

            Example: [
                {'name': 'Moderator', 'type': 'moderator', 'role': 'Manages flow and enforces structure'},
                {'name': 'Proponent', 'type': 'perspective', 'role': 'Expert arguing for position A'},
                {'name': 'Skeptic', 'type': 'perspective', 'role': 'Expert arguing for position B'},
                {'name': 'Researcher', 'type': 'scientist', 'role': 'Tests claims with experiments'},
                {'name': 'Synthesizer', 'type': 'synthesizer', 'role': 'Tracks convergence'},
            ]
        max_rounds: Maximum number of refinement rounds (default 5)
        model: LLM model name to prefix agent names (e.g., "SWE-1.6")
    """
    if not isinstance(agent_configs, list):
        return f"Error: agent_configs must be a list of agent configurations, got {type(agent_configs).__name__}. Example: [{{'name': 'Moderator', 'type': 'moderator', 'role': 'Manages flow'}}]"
    session = manager.create_session(topic, goals, agent_configs, max_rounds, model)
    return f"Consensus session created: {session.id}\nTopic: {topic}\nGoals: {goals}\nAgents: {len(session.agents)}\nMax rounds: {max_rounds}\nModel: {model}\nUse session_id '{session.id}' to interact with this session."


@mcp.tool
def get_state(session_id: str) -> str:
    """Retrieve the current state of a consensus session.

    Args:
        session_id: The ID of the consensus session
    """
    state = manager.get_state(session_id)
    if not state:
        return f"Session not found: {session_id}"
    lines = [
        f"Session: {state['id']}",
        f"Topic: {state['topic']}",
        f"Goals: {state['goals']}",
        f"Phase: {state['phase']}",
        f"Round: {state['round']}/{state['max_rounds']}",
        "",
        "Agents:",
    ]
    for agent in state["agents"]:
        lines.append(f"  - {agent['name']} ({agent['type']}): {agent['role']}")
    lines.extend(["", "=== DEBATE ==="])
    for contrib in state["contributions"]:
        agent_type_emoji = {
            "scientist": "[SCI]",
            "perspective": "[PER]",
            "synthesizer": "[SYN]",
            "moderator": "[MOD]",
        }.get(contrib["agent_type"], "[?]")
        lines.append(f"\n{agent_type_emoji} {contrib['agent_name']}:")
        lines.append(f"  {contrib['content']}")
        if contrib["evidence"]:
            lines.append(f"  Evidence: {contrib['evidence']}")
        if contrib["challenges"]:
            lines.append(f"  Challenges: {', '.join(contrib['challenges'])}")
    if state["agreements"]:
        lines.extend(["", "Agreements:"])
        for a in state["agreements"]:
            lines.append(f"  + {a}")
    if state["disagreements"]:
        lines.extend(["", "Disagreements:"])
        for d in state["disagreements"]:
            lines.append(f"  - {d}")
    return "\n".join(lines)


def _maybe_reopen_session(
    session: ConsensusSession, session_id: str, agent_id: str
) -> str | None:
    """Auto-reopen a completed session when a new contribution is made.

    Returns a message if the session was reopened, None otherwise.
    """
    if session.phase == SessionPhase.COMPLETE:
        agent = session.agents.get(agent_id)
        agent_name = agent.name if agent else "Unknown"
        session.phase = SessionPhase.REFINE
        session.round += 1
        lock = manager._acquire_lock()
        try:
            sessions = manager._read_sessions()
            if session_id in sessions:
                sessions[session_id] = session
                manager._write_sessions(sessions)
        finally:
            manager._release_lock(lock)
        return (
            f"Note: Session was in COMPLETE state. "
            f"Auto-reopened to round {session.round} by {agent_name}'s contribution."
        )
    return None


@mcp.tool
def share_reasoning(
    session_id: str, agent_id: str, content: str, evidence: str | None = None
) -> str:
    """Share reasoning with the consensus session.

    If the session is complete, it will be automatically reopened to allow
    further debate.

    Args:
        session_id: The ID of the consensus session
        agent_id: The ID of the agent sharing reasoning
        content: The reasoning or argument to share
        evidence: Optional evidence or data supporting the reasoning
    """
    session = manager.get_session(session_id)
    if not session:
        return f"Session not found: {session_id}"

    reopen_msg = _maybe_reopen_session(session, session_id, agent_id)

    contribution = manager.add_contribution(session_id, agent_id, content, evidence)
    if not contribution:
        return "Failed to add contribution. Check session_id and agent_id."

    result = f"Contribution added: {contribution.id}\n{content[:200]}..."
    if reopen_msg:
        result = f"{reopen_msg}\n{result}"
    return result


@mcp.tool
def run_experiment(
    session_id: str,
    agent_id: str,
    hypothesis: str,
    code: str,
) -> str:
    """Run an experiment to test a hypothesis.

    Args:
        session_id: The ID of the consensus session
        agent_id: The ID of the scientist agent running the experiment
        hypothesis: The hypothesis being tested
        code: Python code to execute
    """
    import io
    import signal
    from contextlib import redirect_stdout

    logger.info(f"Experiment requested by agent {agent_id} in session {session_id}")
    logger.debug(f"Hypothesis: {hypothesis}")
    logger.debug(f"Code length: {len(code)} characters")

    session = manager.get_session(session_id)
    if not session:
        logger.warning(f"Session not found: {session_id}")
        return f"Session not found: {session_id}"

    agent = session.agents.get(agent_id)
    if not agent or agent.agent_type != AgentType.SCIENTIST:
        logger.warning(f"Non-scientist agent {agent_id} attempted to run experiment")
        return "Only scientist agents can run experiments."

    # Restricted execution environment for security
    safe_builtins = {
        "print": print,
        "len": len,
        "range": range,
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "list": list,
        "dict": dict,
        "tuple": tuple,
        "set": set,
        "sum": sum,
        "min": min,
        "max": max,
        "abs": abs,
        "round": round,
        "sorted": sorted,
        "enumerate": enumerate,
        "zip": zip,
        "map": map,
        "filter": filter,
        "any": any,
        "all": all,
    }

    # Timeout handler to prevent infinite loops
    def timeout_handler(signum, frame):
        raise TimeoutError("Code execution timed out")

    result = None
    error = None
    output_buffer = io.StringIO()

    try:
        # Set 5 second timeout
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(5)

        with redirect_stdout(output_buffer):
            exec(code, {"__builtins__": safe_builtins}, {})

        signal.alarm(0)  # Cancel alarm
        output = output_buffer.getvalue()
        result = output
        logger.info(f"Experiment completed successfully in session {session_id}")
    except TimeoutError as e:
        error = f"Execution timeout: {str(e)}"
        logger.warning(f"Experiment timed out in session {session_id}")
    except Exception as e:
        error = str(e)
        logger.warning(f"Experiment failed in session {session_id}: {error}")
    finally:
        signal.alarm(0)  # Ensure alarm is cancelled

    content = f"Hypothesis: {hypothesis}\nResult: {result or 'No output'}\nError: {error or 'None'}"
    manager.add_contribution(
        session_id, agent_id, content, evidence=result or error
    )
    return f"Experiment completed.\nHypothesis: {hypothesis}\nOutput: {result}\nError: {error}"


@mcp.tool
def challenge_claim(
    session_id: str,
    agent_id: str,
    contribution_id: str,
    challenge: str,
    reason: str,
) -> str:
    """Challenge another agent's claim or reasoning.

    If the session is complete, it will be automatically reopened to allow
    the challenge to be considered.

    Args:
        session_id: The ID of the consensus session
        agent_id: The ID of the agent issuing the challenge
        contribution_id: The ID of the contribution being challenged
        challenge: The specific challenge or question
        reason: The reasoning behind the challenge
    """
    session = manager.get_session(session_id)
    if not session:
        return f"Session not found: {session_id}"

    reopen_msg = _maybe_reopen_session(session, session_id, agent_id)

    contribution = next(
        (c for c in session.contributions if c.id == contribution_id), None
    )
    if not contribution:
        return f"Contribution not found: {contribution_id}"

    contribution.challenges.append(f"{challenge}: {reason}")
    lock = manager._acquire_lock()
    try:
        sessions = manager._read_sessions()
        if session_id in sessions:
            sessions[session_id] = session
            manager._write_sessions(sessions)
    finally:
        manager._release_lock(lock)
    content = f"Challenged {contribution.agent_name}: {challenge}\nReason: {reason}"
    manager.add_contribution(session_id, agent_id, content)

    result = f"Challenge issued: {challenge}\nAgainst: {contribution.agent_name}'s contribution"
    if reopen_msg:
        result = f"{reopen_msg}\n{result}"
    return result


@mcp.tool
def summarize(session_id: str) -> str:
    """Get a summary of current consensus state.

    Args:
        session_id: The ID of the consensus session
    """
    state = manager.get_state(session_id)
    if not state:
        return f"Session not found: {session_id}"

    lines = [
        "## Consensus Summary",
        f"**Topic**: {state['topic']}",
        f"**Phase**: {state['phase']} (Round {state['round']}/{state['max_rounds']})",
        "",
    ]
    if state["agreements"]:
        lines.append("### Agreements")
        for a in state["agreements"]:
            lines.append(f"- {a}")
        lines.append("")
    if state["disagreements"]:
        lines.append("### Disagreements")
        for d in state["disagreements"]:
            lines.append(f"- {d}")
        lines.append("")
    lines.append(f"### Contributions: {len(state['contributions'])} total")
    return "\n".join(lines)


@mcp.tool
def health_check() -> str:
    """Check the health status of the Consensus MCP server.

    Returns:
        Server health status including service name, status, and session count.
    """
    sessions = manager.list_all_sessions()
    return (
        f"Consensus MCP Server Status:\n"
        f"- Status: healthy\n"
        f"- Service: consensus-mcp\n"
        f"- Active sessions: {len(sessions)}\n"
        f"- Version: 3.2.4"
    )


@mcp.tool
def prompt_agent(session_id: str, agent_id: str, instruction: str) -> str:
    """Prompt a specific agent to contribute to the session.

    This tool is primarily used by the moderator to direct agents to take specific actions.
    It creates a system prompt that can be used by the orchestrator to guide the agent's next contribution.

    Args:
        session_id: The ID of the consensus session
        agent_id: The ID of the agent to prompt
        instruction: Specific instruction for what the agent should do

    Returns:
        Confirmation of the prompt with guidance for the orchestrator
    """
    session = manager.get_session(session_id)
    if not session:
        return f"Session not found: {session_id}"

    agent = session.agents.get(agent_id)
    if not agent:
        return f"Agent not found: {agent_id}"

    return (
        f"Prompt generated for {agent.name} ({agent.agent_type.value}):\n"
        f"Instruction: {instruction}\n"
        f"Current phase: {session.phase.value}\n"
        f"Round: {session.round}/{session.max_rounds}\n"
        f"Orchestrator should now call {agent.name} with this instruction."
    )


@mcp.tool
def get_next_actions(session_id: str) -> str:
    """Get recommended next actions based on the current session phase.

    This tool provides guidance to orchestrators about which agents should be called
    and what they should do based on the current phase of the consensus session.

    Args:
        session_id: The ID of the consensus session

    Returns:
        Recommended next actions including which agents to call and what tools to use
    """
    session = manager.get_session(session_id)
    if not session:
        return f"Session not found: {session_id}"

    phase_actions = {
        SessionPhase.CLARIFICATION: [
            "Use ask_question to ask the user clarifying questions about the topic/goals",
            "Wait for user to answer questions using submit_answer",
            "Once clarification is complete, use advance_phase to move to 'setup' phase"
        ],
        SessionPhase.SETUP: [
            "Call moderator to introduce topic and set goals using share_reasoning",
            "Use advance_phase to move to 'position' phase"
        ],
        SessionPhase.POSITION: [
            "Call all perspective agents to share initial views using share_reasoning",
            "Ensure each agent has contributed at least once",
            "Use advance_phase to move to 'testing' phase when all perspectives shared"
        ],
        SessionPhase.TESTING: [
            "Call scientist agent to run experiments using run_experiment",
            "Review experimental results",
            "Use advance_phase to move to 'challenge' phase when testing complete"
        ],
        SessionPhase.CHALLENGE: [
            "Call perspective agents to dispute claims using challenge_claim",
            "Encourage agents to question reasoning and evidence",
            "Use advance_phase to move to 'synthesis' phase when challenges resolved"
        ],
        SessionPhase.SYNTHESIS: [
            "Call synthesizer to analyze convergence using summarize",
            "Call synthesizer to identify agreements using add_agreement",
            "Call synthesizer to identify disagreements using add_disagreement",
            "Use advance_phase to move to 'refine' phase when synthesis complete"
        ],
        SessionPhase.REFINE: [
            "Call agents to address gaps and update positions using share_reasoning",
            "If consensus emerging, use advance_phase to move to 'convergence'",
            "If max rounds reached, move to 'complete' phase"
        ],
        SessionPhase.CONVERGENCE: [
            "Call synthesizer to declare consensus using declare_consensus",
            "Or call moderator to end session without consensus",
            "Use advance_phase to move to 'complete' phase"
        ],
        SessionPhase.COMPLETE: [
            "Session is complete - no further actions needed",
            "Use get_state to review final consensus"
        ]
    }

    actions = phase_actions.get(session.phase, ["Unknown phase - check session state"])

    result = [
        f"Current phase: {session.phase.value}",
        f"Round: {session.round}/{session.max_rounds}",
        f"Agents in session: {len(session.agents)}",
        f"Contributions so far: {len(session.contributions)}",
        "",
        "Recommended next actions:",
    ]
    for i, action in enumerate(actions, 1):
        result.append(f"{i}. {action}")

    result.append("")
    result.append("Agent types present:")
    for agent in session.agents.values():
        result.append(f"- {agent.name} ({agent.agent_type.value}): {agent.role}")

    return "\n".join(result)


@mcp.tool
def declare_consensus(session_id: str, statement: str) -> str:
    """Declare that consensus has been reached.

    Args:
        session_id: The ID of the consensus session
        statement: The consensus statement
    """
    session = manager.get_session(session_id)
    if not session:
        return f"Session not found: {session_id}"

    manager.set_phase(session_id, SessionPhase.COMPLETE)
    manager.add_agreement(session_id, f"CONSENSUS: {statement}")
    return f"Consensus declared!\nStatement: {statement}\nThis session is now complete."


@mcp.tool
def reopen_session(session_id: str, agent_id: str, reason: str) -> str:
    """Reopen a completed session for further debate.

    Allows a new or existing agent to challenge a previously declared consensus
    and continue the discussion. The original consensus statement is preserved
    in the agreements list for reference.

    Args:
        session_id: The ID of the consensus session to reopen
        agent_id: The ID of the agent requesting to reopen
        reason: Reason for reopening (e.g., "New evidence to consider" or "Challenge to consensus")
    """
    session = manager.get_session(session_id)
    if not session:
        return f"Session not found: {session_id}"

    if session.phase != SessionPhase.COMPLETE:
        return f"Session is not complete (current phase: {session.phase.value}). No need to reopen."

    agent = session.agents.get(agent_id)
    if not agent:
        return f"Agent not found: {agent_id} in session {session_id}"

    # Move back to refine phase and increment round
    session.phase = SessionPhase.REFINE
    session.round += 1
    lock = manager._acquire_lock()
    try:
        sessions = manager._read_sessions()
        if session_id in sessions:
            sessions[session_id] = session
            manager._write_sessions(sessions)
    finally:
        manager._release_lock(lock)

    # Add a contribution noting the reopening
    reopen_content = f"Session reopened by {agent.name}: {reason}"
    manager.add_contribution(session_id, agent_id, reopen_content)

    return (
        f"Session reopened by {agent.name} at round {session.round}.\n"
        f"Reason: {reason}\n"
        f"The previous consensus statement is preserved but open to challenge. "
        f"New contributions can now be added."
    )


@mcp.tool
def advance_to_phase(session_id: str, phase: str) -> str:
    """Advance the session to a specific phase.

    Args:
        session_id: The ID of the consensus session
        phase: The phase to advance to (setup, position, testing, challenge, synthesis, refine, convergence, complete)
    """
    try:
        target_phase = SessionPhase(phase.lower())
    except ValueError:
        return f"Invalid phase. Valid phases: {[p.value for p in SessionPhase]}"

    manager.set_phase(session_id, target_phase)
    return f"Session advanced to: {target_phase.value}"


@mcp.tool
def get_raw_state(session_id: str) -> dict[str, Any]:
    """Get raw session state as JSON with agent IDs.

    Args:
        session_id: The ID of the consensus session
    """
    state = manager.get_state(session_id)
    if not state:
        return {"error": f"Session not found: {session_id}"}
    return state


@mcp.tool
def list_sessions() -> str:
    """List all active consensus sessions."""
    sessions = manager.list_all_sessions()
    if not sessions:
        return "No active sessions"
    lines = ["Active Sessions:"]
    for session in sessions:
        lines.append(
            f"  - {session.id}: {session.topic} ({session.phase.value}, round {session.round})"
        )
    return "\n".join(lines)


@mcp.tool
def add_agent(
    session_id: str,
    name: str,
    agent_type: str,
    role: str = "",
    model: str = "default",
) -> str:
    """Add a new agent to an existing session.

    This allows new perspectives to join an ongoing or completed debate.
    The new agent can immediately contribute using their assigned agent_id.

    Args:
        session_id: The ID of the consensus session
        name: The agent's name
        agent_type: The type of agent to add:
            - 'scientist': Can run experiments via run_experiment to test hypotheses with code.
              Add when testable claims need empirical validation.
            - 'perspective': Provides domain expertise and challenges assumptions from specific angles.
              Add when a new viewpoint or expertise area is missing from the debate.
              Always provide a descriptive 'role' (e.g., "Security expert" or "Performance engineer").
            - 'synthesizer': Tracks convergence, identifies agreements/disagreements.
              Add if the session lacks someone tracking consensus progress.
            - 'moderator': Manages session flow and phase transitions.
              Typically only 1 moderator per session.
        role: The agent's role or expertise description. Especially important for perspective
            agents to differentiate their viewpoint (e.g., "Expert in Rails geospatial stack").
        model: The LLM model name to prefix the agent name
    """
    try:
        agent_type_enum = AgentType(agent_type.lower())
    except ValueError:
        return f"Invalid agent_type. Valid types: {[t.value for t in AgentType]}"

    agent = manager.add_agent(session_id, name, agent_type_enum, role, model)
    if not agent:
        return f"Failed to add agent. Session not found: {session_id}"

    return (
        f"Agent added successfully!\n"
        f"Name: {agent.name}\n"
        f"ID: {agent.id}\n"
        f"Type: {agent.agent_type.value}\n"
        f"Role: {agent.role}\n"
        f"Use agent_id '{agent.id}' to contribute to this session."
    )


@mcp.tool
def add_agreement(session_id: str, agreement: str) -> str:
    """Add an agreement point to the consensus session.

    Args:
        session_id: The ID of the consensus session
        agreement: The agreement statement
    """
    if manager.add_agreement(session_id, agreement):
        return f"Agreement added: {agreement}"
    return f"Session not found: {session_id}"


@mcp.tool
def add_disagreement(session_id: str, disagreement: str) -> str:
    """Add a disagreement point to the consensus session.

    Args:
        session_id: The ID of the consensus session
        disagreement: The disagreement statement
    """
    if manager.add_disagreement(session_id, disagreement):
        return f"Disagreement noted: {disagreement}"
    return f"Session not found: {session_id}"


@mcp.tool
def clear_all_sessions() -> str:
    """Clear all consensus sessions from memory and storage."""
    count = manager.clear_all_sessions()
    return f"Cleared {count} sessions"


@mcp.tool
def delete_session(session_id: str) -> str:
    """Delete a specific consensus session.

    Args:
        session_id: The ID of the consensus session to delete
    """
    if manager.delete_session(session_id):
        return f"Session deleted: {session_id}"
    return f"Session not found: {session_id}"


@mcp.tool
def ask_question(session_id: str, question: str) -> str:
    """Ask a question to the user in the clarification phase.

    Use this tool when you need clarification from the user before starting the debate.
    The user can answer the question through the chat interface or web UI.

    Args:
        session_id: The ID of the consensus session
        question: The question to ask the user

    Returns:
        The question ID and confirmation that it was added
    """
    question_obj = manager.ask_question(session_id, question)
    if not question_obj:
        return f"Failed to ask question. Session not found: {session_id}"

    return (
        f"Question asked successfully!\n"
        f"Question ID: {question_obj.id}\n"
        f"Question: {question}\n"
        f"Wait for the user to answer using submit_answer or through the web UI."
    )


@mcp.tool
def submit_answer(session_id: str, question_id: str, answer: str) -> str:
    """Submit an answer to a question that was asked during clarification.

    Use this tool to provide the user's answer to a previously asked question.

    Args:
        session_id: The ID of the consensus session
        question_id: The ID of the question to answer
        answer: The answer text

    Returns:
        Confirmation that the answer was submitted
    """
    if manager.submit_answer(session_id, question_id, answer):
        return f"Answer submitted successfully for question {question_id}"
    return f"Failed to submit answer. Session or question not found."


@mcp.tool
def report_bug(session_id: str, agent_id: str, bug_report: dict[str, Any]) -> str:
    """Report a bug found during the implementing phase.

    This tool is used by bug hunter agents to report bugs they find in changed files.
    The bug report should include details like file path, description, severity, etc.

    Args:
        session_id: The ID of the consensus session
        agent_id: The ID of the bug hunter agent reporting the bug
        bug_report: Dictionary containing bug details. Should include:
            - file: The file where the bug was found
            - description: Description of the bug
            - severity: Severity level (low, medium, high, critical)
            - line_number: Optional line number where bug occurs
            - code_snippet: Optional code snippet showing the bug

    Returns:
        Confirmation that the bug was reported
    """
    if manager.report_bug(session_id, agent_id, bug_report):
        return f"Bug reported successfully by agent {agent_id}"
    return f"Failed to report bug. Session or agent not found, or agent is not a bug hunter."


@mcp.tool
def verify_bug(session_id: str, agent_id: str, bug_index: int, verified: bool, comment: str = "") -> str:
    """Verify a bug report from a bug hunter agent.

    This tool is used by the code verification agent to verify bug reports
    submitted by bug hunter agents.

    Args:
        session_id: The ID of the consensus session
        agent_id: The ID of the code verification agent
        bug_index: The index of the bug in the session's bugs list
        verified: Whether the bug is verified as valid (true) or invalid (false)
        comment: Optional comment explaining the verification decision

    Returns:
        Confirmation that the bug verification was recorded
    """
    if manager.verify_bug(session_id, agent_id, bug_index, verified, comment):
        status = "verified" if verified else "rejected"
        return f"Bug {bug_index} {status} by code verification agent"
    return f"Failed to verify bug. Session, agent, or bug not found, or agent is not a code verification agent."


def main():
    """Entry point for running the MCP server.

    Run with stdio transport by default (for MCP clients).
    Run with HTTP transport when --http flag is provided (for web dashboard).
    """
    import sys

    # Check if HTTP mode is requested
    if "--http" in sys.argv:
        mcp.run(transport="http", host="0.0.0.0", port=8000, stateless=True)
    else:
        mcp.run()


@mcp.custom_route("/sessions", methods=["GET"])
async def list_sessions_html(request: Request) -> HTMLResponse:
    """Serve the sessions dashboard HTML page."""
    template = env.get_template("sessions.html")

    sessions_data = []
    sessions = manager.list_all_sessions()
    if sessions:
        for session in sessions:
            state = manager.get_state(session.id)
            sessions_data.append(
                {
                    "id": session.id,
                    "topic": state["topic"],
                    "goals": state["goals"],
                    "phase": state["phase"],
                    "round": state["round"],
                    "max_rounds": state["max_rounds"],
                    "agents_count": len(state["agents"]),
                    "contrib_count": len(state["contributions"]),
                    "created_at": state["created_at"],
                }
            )
        # Sort by created_at descending (newest first)
        sessions_data.sort(key=lambda x: x["created_at"], reverse=True)

    html = template.render(sessions=sessions_data)
    return HTMLResponse(html)


@mcp.custom_route("/sessions/create", methods=["GET"])
async def create_session_form(request: Request) -> HTMLResponse:
    """Serve the create session form."""
    template = env.get_template("create_session.html")
    html = template.render()
    return HTMLResponse(html)


@mcp.custom_route("/sessions/create", methods=["POST"])
async def create_session_handler(request: Request) -> HTMLResponse:
    """Handle create session form submission."""
    form_data = await request.form()
    topic = form_data.get("topic", "").strip()
    goals = form_data.get("goals", "").strip()
    max_rounds = int(form_data.get("max_rounds", 5))

    if not topic or not goals:
        return HTMLResponse(
            "<h1>Error: Topic and goals are required</h1>", status_code=400
        )

    # Create session with just a default moderator
    session = manager.create_session(
        topic=topic,
        goals=goals,
        agent_configs=None,  # Will create default moderator
        max_rounds=max_rounds,
        model="default",
    )

    logger.info(f"Web: Created session {session.id} via dashboard")

    # Redirect to the new session
    return HTMLResponse(
        f"<script>window.location.href='/session/{session.id}';</script>",
        status_code=302,
    )


@mcp.custom_route("/api/sessions", methods=["GET"])
async def list_sessions_json(request: Request) -> JSONResponse:
    """Serve the sessions data as JSON for AJAX polling."""
    sessions_data = []
    sessions = manager.list_all_sessions()
    if sessions:
        for session in sessions:
            state = manager.get_state(session.id)
            sessions_data.append(
                {
                    "id": session.id,
                    "topic": state["topic"],
                    "goals": state["goals"],
                    "phase": state["phase"],
                    "round": state["round"],
                    "max_rounds": state["max_rounds"],
                    "agents_count": len(state["agents"]),
                    "contrib_count": len(state["contributions"]),
                    "created_at": state["created_at"],
                }
            )
        # Sort by created_at descending (newest first)
        sessions_data.sort(key=lambda x: x["created_at"], reverse=True)
    return JSONResponse(sessions_data)


@mcp.custom_route("/api/session/{session_id}", methods=["GET"])
async def session_detail_json(request: Request) -> JSONResponse:
    """Serve the session detail data as JSON for AJAX polling."""
    session_id = request.path_params["session_id"]
    state = manager.get_state(session_id)
    if not state:
        return JSONResponse({"error": "Session not found"}, status_code=404)
    return JSONResponse(state)


@mcp.custom_route("/api/sessions/create", methods=["POST"])
async def create_session_json(request: Request) -> JSONResponse:
    """Create a new session via JSON API (bypasses MCP tool layer)."""
    try:
        body = await request.json()
        topic = body.get("topic", "").strip()
        goals = body.get("goals", "").strip()
        agent_configs = body.get("agent_configs")
        max_rounds = body.get("max_rounds", 5)
        model = body.get("model", "default")

        if not topic or not goals:
            return JSONResponse(
                {"error": "Topic and goals are required"}, status_code=400
            )

        session = manager.create_session(
            topic=topic,
            goals=goals,
            agent_configs=agent_configs,
            max_rounds=max_rounds,
            model=model,
        )

        logger.info(f"API: Created session {session.id}")

        return JSONResponse(
            {
                "id": session.id,
                "topic": session.topic,
                "goals": session.goals,
                "phase": session.phase.value,
                "round": session.round,
                "max_rounds": session.max_rounds,
                "agents": [
                    {
                        "id": a.id,
                        "name": a.name,
                        "type": a.agent_type.value,
                        "role": a.role,
                    }
                    for a in session.agents.values()
                ],
            }
        )
    except Exception as e:
        logger.error(f"API: Failed to create session: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@mcp.custom_route("/session/{session_id}", methods=["GET"])
async def session_detail_html(request: Request) -> HTMLResponse:
    """Serve a specific session's detail page."""
    session_id = request.path_params["session_id"]

    session = manager.get_session(session_id)
    if not session:
        return HTMLResponse(
            f"<h1>Session not found: {session_id}</h1>", status_code=404
        )

    state = manager.get_state(session_id)

    # Add agent type labels to contributions
    agent_type_labels = {
        "scientist": "Scientist",
        "perspective": "Perspective",
        "synthesizer": "Synthesizer",
        "moderator": "Moderator",
    }

    for contrib in state["contributions"]:
        contrib["agent_type_label"] = agent_type_labels.get(
            contrib["agent_type"], "Agent"
        )

    template = env.get_template("session_detail.html")
    html = template.render(state=state)
    return HTMLResponse(html)


@mcp.custom_route("/session/{session_id}/edit-goals", methods=["POST"])
async def edit_session_goals(request: Request) -> HTMLResponse:
    """Handle session goals edit form submission."""
    session_id = request.path_params["session_id"]

    session = manager.get_session(session_id)
    if not session:
        return HTMLResponse(
            f"<h1>Session not found: {session_id}</h1>", status_code=404
        )

    # Parse form data
    form_data = await request.form()
    goals = form_data.get("goals", "").strip()

    if not goals:
        return HTMLResponse("<h1>Goals cannot be empty</h1>", status_code=400)

    # Update the goals
    if manager.update_goals(session_id, goals):
        logger.info(f"Web: Goals updated for session {session_id}")
        # Redirect back to the session detail page
        return HTMLResponse(
            f"<script>window.location.href='/session/{session_id}';</script>",
            status_code=302,
        )
    else:
        return HTMLResponse("<h1>Failed to update goals</h1>", status_code=500)


@mcp.custom_route("/session/{session_id}/comment", methods=["POST"])
async def add_user_comment(request: Request) -> HTMLResponse:
    """Handle user comment submission for a session."""
    session_id = request.path_params["session_id"]

    session = manager.get_session(session_id)
    if not session:
        return HTMLResponse(
            f"<h1>Session not found: {session_id}</h1>", status_code=404
        )

    # Parse form data
    form_data = await request.form()
    content = form_data.get("content", "")
    model = form_data.get("model", "Human")

    if not content:
        return HTMLResponse("<h1>Comment content is required</h1>", status_code=400)

    # Create a user agent for this contribution
    agent_name = f"{model}-User" if model and model != "Human" else "User"
    user_agent = manager.add_agent(
        session_id,
        name=agent_name,
        agent_type=AgentType.PERSPECTIVE,
        role="Human participant",
        model=model,
    )
    if not user_agent:
        return HTMLResponse("<h1>Failed to add agent to session</h1>", status_code=500)

    # Add the contribution
    contribution = manager.add_contribution(session_id, user_agent.id, content)
    if not contribution:
        return HTMLResponse(
            "<h1>Failed to add contribution to session</h1>", status_code=500
        )

    # If session is complete, move it back to refine phase to allow continuation
    if session.phase == SessionPhase.COMPLETE:
        manager.set_phase(session_id, SessionPhase.REFINE)
        # Need to reload session to get updated round
        session = manager.get_session(session_id)
        if session:
            session.round += 1
            session.phase = SessionPhase.REFINE
            # Save the updated session
            lock = manager._acquire_lock()
            try:
                sessions = manager._read_sessions()
                if session_id in sessions:
                    sessions[session_id] = session
                    manager._write_sessions(sessions)
            finally:
                manager._release_lock(lock)
    logger.info(f"User comment added to session {session_id}")

    # Redirect back to session detail page
    return HTMLResponse(
        f"<script>window.location.href='/session/{session_id}';</script>",
        status_code=302,
    )


@mcp.custom_route("/static/{file_path:path}", methods=["GET"])
async def serve_static(request: Request) -> HTMLResponse:
    """Serve static files (CSS)."""
    file_path = request.path_params["file_path"]
    static_dir = Path(__file__).parent / "templates"
    file = static_dir / file_path

    if not file.exists():
        return HTMLResponse("File not found", status_code=404)

    content = file.read_text()
    return HTMLResponse(content, media_type="text/css")


@mcp.custom_route("/sessions/clear", methods=["POST"])
async def clear_sessions(request: Request) -> HTMLResponse:
    """Clear all sessions and redirect back to sessions list."""
    count = manager.clear_all_sessions()
    logger.info(f"Web request: Cleared {count} sessions")
    # Redirect back to sessions page
    return HTMLResponse(
        "<script>window.location.href='/sessions';</script>", status_code=302
    )


@mcp.custom_route("/session/{session_id}/delete", methods=["POST"])
async def delete_session_handler(request: Request) -> HTMLResponse:
    """Delete a specific session and redirect back to sessions list."""
    session_id = request.path_params["session_id"]
    if manager.delete_session(session_id):
        logger.info(f"Web request: Deleted session {session_id}")
    else:
        logger.warning(f"Web request: Failed to delete session {session_id}")
    # Redirect back to sessions page
    return HTMLResponse(
        "<script>window.location.href='/sessions';</script>", status_code=302
    )


@mcp.custom_route("/session/{session_id}/add-agent", methods=["POST"])
async def add_agent_handler(request: Request) -> HTMLResponse:
    """Handle add agent form submission."""
    session_id = request.path_params["session_id"]

    session = manager.get_session(session_id)
    if not session:
        return HTMLResponse(
            f"<h1>Session not found: {session_id}</h1>", status_code=404
        )

    form_data = await request.form()
    name = form_data.get("name", "").strip()
    agent_type_str = form_data.get("agent_type", "perspective").strip()
    role = form_data.get("role", "").strip()
    model = form_data.get("model", "default").strip()

    if not name or not agent_type_str:
        return HTMLResponse(
            "<h1>Error: Name and agent type are required</h1>", status_code=400
        )

    try:
        agent_type = AgentType(agent_type_str)
    except ValueError:
        return HTMLResponse(
            f"<h1>Error: Invalid agent type: {agent_type_str}</h1>", status_code=400
        )

    agent = manager.add_agent(
        session_id, name=name, agent_type=agent_type, role=role, model=model
    )
    if not agent:
        return HTMLResponse("<h1>Failed to add agent to session</h1>", status_code=500)

    logger.info(f"Web: Agent {name} added to session {session_id}")

    return HTMLResponse(
        f"<script>window.location.href='/session/{session_id}';</script>",
        status_code=302,
    )


@mcp.custom_route("/session/{session_id}/advance-phase", methods=["POST"])
async def advance_phase_handler(request: Request) -> HTMLResponse:
    """Handle advance phase form submission."""
    session_id = request.path_params["session_id"]

    session = manager.get_session(session_id)
    if not session:
        return HTMLResponse(
            f"<h1>Session not found: {session_id}</h1>", status_code=404
        )

    form_data = await request.form()
    target_phase_str = form_data.get("phase", "").strip()

    if target_phase_str:
        try:
            target_phase = SessionPhase(target_phase_str)
            success = manager.set_phase(session_id, target_phase)
            if success:
                logger.info(f"Web: Session {session_id} advanced to {target_phase_str}")
            else:
                return HTMLResponse("<h1>Failed to advance phase</h1>", status_code=500)
        except ValueError:
            return HTMLResponse(
                f"<h1>Error: Invalid phase: {target_phase_str}</h1>", status_code=400
            )
    else:
        new_phase = manager.advance_phase(session_id)
        if new_phase:
            logger.info(f"Web: Session {session_id} advanced to {new_phase.value}")
        else:
            return HTMLResponse("<h1>Failed to advance phase</h1>", status_code=500)

    return HTMLResponse(
        f"<script>window.location.href='/session/{session_id}';</script>",
        status_code=302,
    )


@mcp.custom_route("/session/{session_id}/declare-consensus", methods=["POST"])
async def declare_consensus_handler(request: Request) -> HTMLResponse:
    """Handle declare consensus form submission."""
    session_id = request.path_params["session_id"]

    session = manager.get_session(session_id)
    if not session:
        return HTMLResponse(
            f"<h1>Session not found: {session_id}</h1>", status_code=404
        )

    form_data = await request.form()
    statement = form_data.get("statement", "").strip()

    if not statement:
        return HTMLResponse(
            "<h1>Error: Consensus statement is required</h1>", status_code=400
        )

    success = manager.add_agreement(session_id, f"CONSENSUS: {statement}")
    if success:
        manager.set_phase(session_id, SessionPhase.COMPLETE)
        logger.info(f"Web: Consensus declared for session {session_id}")
    else:
        return HTMLResponse("<h1>Failed to declare consensus</h1>", status_code=500)

    return HTMLResponse(
        f"<script>window.location.href='/session/{session_id}';</script>",
        status_code=302,
    )


@mcp.custom_route("/session/{session_id}/challenge", methods=["POST"])
async def challenge_claim_handler(request: Request) -> HTMLResponse:
    """Handle challenge claim form submission."""
    session_id = request.path_params["session_id"]

    session = manager.get_session(session_id)
    if not session:
        return HTMLResponse(
            f"<h1>Session not found: {session_id}</h1>", status_code=404
        )

    form_data = await request.form()
    contribution_id = form_data.get("contribution_id", "").strip()
    challenge_text = form_data.get("challenge", "").strip()

    if not contribution_id or not challenge_text:
        return HTMLResponse(
            "<h1>Error: Contribution ID and challenge text are required</h1>",
            status_code=400,
        )

    contribution = None
    for contrib in session.contributions:
        if contrib.id == contribution_id:
            contribution = contrib
            break

    if not contribution:
        return HTMLResponse(
            f"<h1>Contribution not found: {contribution_id}</h1>", status_code=404
        )

    if challenge_text not in contribution.challenges:
        contribution.challenges.append(challenge_text)

    lock = manager._acquire_lock()
    try:
        sessions = manager._read_sessions()
        if session_id in sessions:
            sessions[session_id] = session
            manager._write_sessions(sessions)
    finally:
        manager._release_lock(lock)

    logger.info(f"Web: Challenge added to contribution {contribution_id}")

    return HTMLResponse(
        f"<script>window.location.href='/session/{session_id}';</script>",
        status_code=302,
    )


@mcp.custom_route("/session/{session_id}/add-agreement", methods=["POST"])
async def add_agreement_handler(request: Request) -> HTMLResponse:
    """Handle add agreement form submission."""
    session_id = request.path_params["session_id"]

    session = manager.get_session(session_id)
    if not session:
        return HTMLResponse(
            f"<h1>Session not found: {session_id}</h1>", status_code=404
        )

    form_data = await request.form()
    agreement = form_data.get("agreement", "").strip()

    if not agreement:
        return HTMLResponse(
            "<h1>Error: Agreement text is required</h1>", status_code=400
        )

    success = manager.add_agreement(session_id, agreement)
    if success:
        logger.info(f"Web: Agreement added to session {session_id}")
    else:
        return HTMLResponse("<h1>Failed to add agreement</h1>", status_code=500)

    return HTMLResponse(
        f"<script>window.location.href='/session/{session_id}';</script>",
        status_code=302,
    )


@mcp.custom_route("/session/{session_id}/add-disagreement", methods=["POST"])
async def add_disagreement_handler(request: Request) -> HTMLResponse:
    """Handle add disagreement form submission."""
    session_id = request.path_params["session_id"]

    session = manager.get_session(session_id)
    if not session:
        return HTMLResponse(
            f"<h1>Session not found: {session_id}</h1>", status_code=404
        )

    form_data = await request.form()
    disagreement = form_data.get("disagreement", "").strip()

    if not disagreement:
        return HTMLResponse(
            "<h1>Error: Disagreement text is required</h1>", status_code=400
        )

    success = manager.add_disagreement(session_id, disagreement)
    if success:
        logger.info(f"Web: Disagreement added to session {session_id}")
    else:
        return HTMLResponse("<h1>Failed to add disagreement</h1>", status_code=500)

    return HTMLResponse(
        f"<script>window.location.href='/session/{session_id}';</script>",
        status_code=302,
    )


@mcp.custom_route("/session/{session_id}/export", methods=["GET"])
async def export_session_handler(request: Request) -> JSONResponse:
    """Export session data as JSON."""
    session_id = request.path_params["session_id"]

    state = manager.get_state(session_id)
    if not state:
        return JSONResponse({"error": "Session not found"}, status_code=404)

    return JSONResponse(state)


@mcp.custom_route("/session/{session_id}/ask-question", methods=["POST"])
async def ask_question_handler(request: Request) -> HTMLResponse:
    """Handle ask question form submission."""
    session_id = request.path_params["session_id"]

    session = manager.get_session(session_id)
    if not session:
        return HTMLResponse(
            f"<h1>Session not found: {session_id}</h1>", status_code=404
        )

    form_data = await request.form()
    question = form_data.get("question", "").strip()

    if not question:
        return HTMLResponse(
            "<h1>Error: Question text is required</h1>", status_code=400
        )

    question_obj = manager.ask_question(session_id, question)
    if not question_obj:
        return HTMLResponse("<h1>Failed to add question</h1>", status_code=500)

    logger.info(f"Web: Question added to session {session_id}")

    return HTMLResponse(
        f"<script>window.location.href='/session/{session_id}';</script>",
        status_code=302,
    )


@mcp.custom_route("/session/{session_id}/answer-question", methods=["POST"])
async def answer_question_handler(request: Request) -> HTMLResponse:
    """Handle answer question form submission."""
    session_id = request.path_params["session_id"]

    session = manager.get_session(session_id)
    if not session:
        return HTMLResponse(
            f"<h1>Session not found: {session_id}</h1>", status_code=404
        )

    form_data = await request.form()
    question_id = form_data.get("question_id", "").strip()
    answer = form_data.get("answer", "").strip()

    if not question_id or not answer:
        return HTMLResponse(
            "<h1>Error: Question ID and answer text are required</h1>",
            status_code=400,
        )

    success = manager.submit_answer(session_id, question_id, answer)
    if success:
        logger.info(f"Web: Answer submitted for question {question_id} in session {session_id}")
    else:
        return HTMLResponse("<h1>Failed to submit answer</h1>", status_code=500)

    return HTMLResponse(
        f"<script>window.location.href='/session/{session_id}';</script>",
        status_code=302,
    )


@mcp.custom_route("/health", methods=["GET"])
async def health_check_http(request: Request) -> JSONResponse:
    """Health check endpoint for Docker and monitoring."""
    return JSONResponse({"status": "healthy", "service": "consensus-mcp"})


if __name__ == "__main__":
    main()
