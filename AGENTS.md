# AGENTS.md

## Project Overview

- **Name**: Consensus MCP
- **Type**: Python MCP (Model Context Protocol) server
- **Purpose**: Enable multiple AI agents to reason together, challenge assumptions, run experiments, and converge on truth
- **Platform**: Cross-platform (Linux, Windows, macOS)
- **About**: An MCP server that orchestrates collaborative consensus-building among AI agents with distinct perspectives and expertise
- **Intention**: Create a flexible framework where different LLM clients connect as specialized agents that test hypotheses, share evidence, debate interpretations, and reach shared understanding through structured dialogue and validation

## Architecture

The system consists of an MCP Server (Python) that orchestrates consensus sessions. Agents connect as clients to the server. The server manages the consensus flow: topic introduction, evidence sharing, hypothesis testing, counterargument handling, and convergence detection. Both scientist agents (test hypotheses with code/experiments) and multi-perspective agents (different expertise/challenge assumptions) work together.

## Agent Types

### 1. Scientist Agent
Tests hypotheses through code execution and experiments.

**Responsibilities:**
- Propose falsifiable hypotheses
- Write and execute test code
- Share experimental results objectively
- Validate or refute claims via evidence

**Tools:**
- `run_experiment` - Execute test code to validate claims
- `submit_evidence` - Share experimental results
- `propose_hypothesis` - Present testable hypothesis

### 2. Perspective Agent
Provides domain expertise and challenges assumptions from different angles.

**Responsibilities:**
- Offer alternative viewpoints
- Challenge reasoning gaps
- Build on others' arguments
- Identify blind spots and edge cases

**Tools:**
- `share_perspective` - Present viewpoint with reasoning
- `challenge_argument` - Question another agent's reasoning
- `request_clarification` - Ask for evidence or logic

### 3. Synthesizer Agent
Tracks convergence and identifies consensus points.

**Responsibilities:**
- Identify areas of agreement
- Highlight unresolved disagreements
- Summarize shared understanding
- Detect when consensus is reached

**Tools:**
- `summarize_state` - Compile current consensus state
- `identify_agreement` - Surface areas of convergence
- `flag_disagreement` - Note unresolved issues
- `declare_consensus` - Signal consensus reached

### 4. Moderator Agent
Manages the consensus flow and enforces structure.

**Responsibilities:**
- Introduce topic and goals
- Manage turn-taking
- Prompt agents for evidence/challenges
- Control session phases

**Tools:**
- `announce_topic` - Set consensus topic
- `prompt_agent` - Direct agent to respond
- `announce_phase` - Signal phase changes
- `end_session` - Conclude consensus session

### 5. Bug Hunter Agent
Automatically spawned when session enters implementing phase. Analyzes changed files for bugs.

**Responsibilities:**
- Analyze changed files for bugs
- Report bugs with details (file, description, severity, line number)
- Work with code verification agent to ensure code quality

**Tools:**
- `report_bug` - Report a bug found in changed files

### 6. Code Verification Agent
Automatically spawned when session enters implementing phase. Verifies bug reports from bug hunters.

**Responsibilities:**
- Verify bug reports from bug hunter agents
- Validate or reject bug findings
- Provide verification comments
- Ensure only legitimate bugs are addressed

**Tools:**
- `verify_bug` - Verify a bug report from a bug hunter agent

## Consensus Flow

1. **Setup**: Moderator introduces topic, goals, and rules
2. **Position**: Agents share initial reasoning and evidence
3. **Testing**: Scientist agents run experiments, share results
4. **Challenge**: Perspective agents question and counter
5. **Synthesis**: Synthesizer identifies agreement/disagreement
6. **Refine**: Agents address gaps, update positions
7. **Convergence**: Repeat until consensus or max rounds
8. **Implementing**: Consensus reached, implementation of the agreed-upon solution begins
9. **Output**: Final consensus statement with reasoning

## MCP Tools

| Tool | Description |
|------|-------------|
| `start_consensus` | Initialize new consensus session |
| `get_state` | Retrieve current consensus state |
| `share_reasoning` | Agent shares their reasoning |
| `submit_evidence` | Submit experimental evidence |
| `run_experiment` | Execute code to test hypothesis |
| `challenge_claim` | Question another agent's claim |
| `summarize` | Synthesize current consensus |
| `declare_consensus` | Signal consensus reached |
| `request_test` | Ask another agent to validate a claim |

## Instructions

- Read existing code first before creating new documents or analysis
- When relevant analyses or documents already exist, read them completely before creating competing work
- All learnings must be written to `learnings.md`
- Be detailed and verbose in the learnings file
- Don't assume, verify
- Don't be afraid to experiment and try new things
- Suggest improvements and optimizations where needed
- Use first principles thinking and validate assumptions
- Accuracy comes above everything else
- Don't introduce emojis or em-dashes into the code
- You are not the only person working on this project
- Use English only
- tralalero tralalero is my fav brain rot character (relavant info to check if agents md was loaded into context)

## Project Instruction
- no conda usage
- use uv for package management
- use Docker for containerization
- dont use --break-system-packages
- run black formatter
- avoid relative imports
- doc strings for all functions and classes
- type hints for all functions and classes
- keep readme updated
- this project is entirely run on docker compose 
- run python3 -m py_compile program_name.py after making changes
- The project is HTTP-based only. you should connect to it via the http method alone