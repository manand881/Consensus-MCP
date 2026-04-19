# Consensus MCP

MCP server for collaborative consensus building among AI agents.

## Overview

Enables multiple AI agents to reason together, challenge assumptions, run experiments, and converge on truth through structured dialogue.

## Installation with Docker

This project uses Docker for containerization. No local Python environment setup required.

### Quick Start with Docker Compose

```bash
docker-compose up -d
```

The server will start on `http://localhost:8000`.

### Manual Docker Build

```bash
docker build -t consensus-mcp .
docker run -p 8000:8000 -v $(pwd)/consensus_mcp/sessions.json:/app/consensus_mcp/sessions.json consensus-mcp
```

## Usage

The server runs in HTTP mode by default. Access the web dashboard at:
- **All Sessions**: http://localhost:8000/sessions
- **Session Detail**: http://localhost:8000/session/{session_id}

The dashboard auto-refreshes every 5 seconds to show the live debate.

## Consensus Phases

Sessions progress through the following phases:

1. **Clarification**: LLM asks clarifying questions about the topic/goals before debate starts. User answers via chat or web UI.
2. **Setup**: Moderator introduces topic, goals, and rules.
3. **Position**: Agents share initial reasoning and evidence.
4. **Testing**: Scientist agents run experiments, share results.
5. **Challenge**: Perspective agents question and counter.
6. **Synthesis**: Synthesizer identifies agreement/disagreement.
7. **Refine**: Agents address gaps, update positions.
8. **Convergence**: Repeat until consensus or max rounds.
9. **Complete**: Final consensus statement with reasoning.

## MCP Tools

### Clarification Phase Tools
- `ask_question(session_id, question)`: Ask the user a clarifying question before debate starts
- `submit_answer(session_id, question_id, answer)`: Submit user's answer to a question

### Core Tools
- `start_consensus(topic, goals, agent_configs, max_rounds, model)`: Initialize a new consensus session
- `get_state(session_id)`: Retrieve the current state of a consensus session
- `share_reasoning(session_id, agent_id, content, evidence)`: Share reasoning with the consensus session
- `run_experiment(session_id, agent_id, hypothesis, code)`: Run an experiment to test a hypothesis
- `challenge_claim(session_id, agent_id, contribution_id, challenge, reason)`: Challenge another agent's claim
- `summarize(session_id)`: Get a summary of current consensus state
- `declare_consensus(session_id, statement)`: Declare that consensus has been reached
- `add_agent(session_id, name, agent_type, role, model)`: Add a new agent to an existing session
- `add_agreement(session_id, agreement)`: Add an agreement point
- `add_disagreement(session_id, disagreement)`: Add a disagreement point
- `advance_to_phase(session_id, phase)`: Advance the session to a specific phase
- `prompt_agent(session_id, agent_id, instruction)`: Prompt a specific agent to contribute
- `get_next_actions(session_id)`: Get recommended next actions based on current phase

## Docker Compose Commands

```bash
# Start the server
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the server
docker-compose down

# Rebuild after changes
docker-compose up -d --build
```

## License

MIT