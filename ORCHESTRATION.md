# Consensus MCP Orchestration Guide

This guide explains how to orchestrate consensus sessions with the Consensus MCP server.

## Important: The MCP Server is Passive

The Consensus MCP server provides tools but **does NOT auto-invoke agents**. External orchestrators (LLM clients, workflow engines, or custom code) must:
- Decide which agent to call
- Call the appropriate MCP tools
- Manage the conversation flow
- Track session phases

## Phase-by-Phase Orchestration

### 1. Setup Phase
**Goal:** Introduce topic and set goals

**Actions:**
- Call moderator to introduce topic using `share_reasoning`
- Moderator should set clear goals and rules
- Use `advance_phase` to move to 'position' phase

**Example:**
```
share_reasoning(
  session_id="xxx",
  agent_id=moderator_id,
  content="Today we'll discuss [topic]. Our goal is to [goals]. Rules: [rules]"
)
advance_phase(session_id="xxx", phase="position")
```

### 2. Position Phase
**Goal:** Agents share initial reasoning and evidence

**Actions:**
- Call each perspective agent to share initial views using `share_reasoning`
- Ensure each agent contributes at least once
- Use `advance_phase` to move to 'testing' phase when all perspectives shared

**Example:**
```
for agent_id in perspective_agent_ids:
  share_reasoning(
    session_id="xxx",
    agent_id=agent_id,
    content="My perspective on [topic] is..."
  )
advance_phase(session_id="xxx", phase="testing")
```

### 3. Testing Phase
**Goal:** Scientist agents run experiments to test claims

**Actions:**
- Call scientist agent to run experiments using `run_experiment`
- Review experimental results
- Use `advance_phase` to move to 'challenge' phase when testing complete

**Example:**
```
run_experiment(
  session_id="xxx",
  agent_id=scientist_id,
  hypothesis="Claim X is true",
  code="print('testing claim X')"
)
advance_phase(session_id="xxx", phase="challenge")
```

### 4. Challenge Phase
**Goal:** Perspective agents dispute claims and question reasoning

**Actions:**
- Call perspective agents to dispute claims using `challenge_claim`
- Encourage agents to question reasoning and evidence
- Use `advance_phase` to move to 'synthesis' phase when challenges resolved

**Example:**
```
challenge_claim(
  session_id="xxx",
  agent_id=agent_id,
  contribution_id="yyy",
  challenge="This claim is flawed because...",
  reason="The evidence doesn't support..."
)
advance_phase(session_id="xxx", phase="synthesis")
```

### 5. Synthesis Phase
**Goal:** Synthesizer identifies agreement/disagreement

**Actions:**
- Call synthesizer to analyze convergence using `summarize`
- Call synthesizer to identify agreements using `add_agreement`
- Call synthesizer to identify disagreements using `add_disagreement`
- Use `advance_phase` to move to 'refine' phase when synthesis complete

**Example:**
```
summarize(session_id="xxx")
add_agreement(session_id="xxx", agreement="All agents agree on X")
add_disagreement(session_id="xxx", disagreement="Agents disagree on Y")
advance_phase(session_id="xxx", phase="refine")
```

### 6. Refine Phase
**Goal:** Agents address gaps and update positions

**Actions:**
- Call agents to address gaps using `share_reasoning`
- If consensus emerging, use `advance_phase` to move to 'convergence'
- If max rounds reached, move to 'complete' phase

**Example:**
```
share_reasoning(
  session_id="xxx",
  agent_id=agent_id,
  content="Based on the synthesis, I now believe..."
)
advance_phase(session_id="xxx", phase="convergence")
```

### 7. Convergence Phase
**Goal:** Declare consensus or end session

**Actions:**
- Call synthesizer to declare consensus using `declare_consensus`
- Or call moderator to end session without consensus
- Use `advance_phase` to move to 'complete' phase

**Example:**
```
declare_consensus(
  session_id="xxx",
  statement="Consensus reached on X with reasoning Y"
)
advance_phase(session_id="xxx", phase="complete")
```

### 8. Complete Phase
**Goal:** Session ends

**Actions:**
- Use `get_state` to review final consensus
- No further actions needed

## Moderator Responsibilities

The moderator should be called **AFTER each phase** to:
- Manage phase transitions
- Use `prompt_agent` to direct specific agents to contribute
- Use `advance_phase` to move to next phase
- Detect stalemates and request evidence from scientist
- Ensure all agents have opportunity to contribute

**Example moderator workflow:**
```
# After position phase
prompt_agent(
  session_id="xxx",
  agent_id=scientist_id,
  instruction="Please run experiments to test the claims made by perspective agents"
)

# After testing phase
prompt_agent(
  session_id="xxx",
  agent_id=synthesizer_id,
  instruction="Please analyze the experimental results and identify areas of agreement"
)
```

## Key Orchestration Patterns

### After scientist provides evidence
- Call synthesizer to analyze
- Use `summarize` to get current state
- Use `add_agreement` or `add_disagreement` to track findings

### After disagreement emerges
- Call moderator to resolve or direct challenge
- Use `prompt_agent` to guide the debate
- Use `challenge_claim` to formally dispute claims

### When consensus reached
- Call synthesizer to declare_consensus
- Move to complete phase
- Archive session results

## Available Tools for Orchestration

### Session Management
- `start_consensus` - Initialize new session
- `get_state` - Retrieve current session state
- `advance_phase` - Move to next phase
- `set_phase` - Set specific phase

### Agent Interaction
- `share_reasoning` - Agent shares reasoning
- `prompt_agent` - Moderator prompts specific agent
- `get_next_actions` - Get phase-specific guidance

### Evidence and Testing
- `run_experiment` - Scientist runs experiment
- `challenge_claim` - Agent disputes claim

### Consensus Tracking
- `add_agreement` - Track agreement points
- `add_disagreement` - Track disagreement points
- `declare_consensus` - Declare consensus reached
- `summarize` - Get consensus summary

### Session Control
- `reopen_session` - Reopen completed session
- `delete_session` - Delete session
- `clear_all_sessions` - Clear all sessions

## Example Orchestration Workflow

```python
# 1. Create session
session = start_consensus(
  topic="What is the best approach for X?",
  goals="Identify the most efficient solution",
  agent_configs=[...]
)

# 2. Setup phase
share_reasoning(session_id, moderator_id, "Let's discuss X...")
advance_phase(session_id, "position")

# 3. Position phase
for agent in perspective_agents:
  share_reasoning(session_id, agent.id, "My view is...")
advance_phase(session_id, "testing")

# 4. Testing phase
run_experiment(session_id, scientist_id, "Hypothesis", "code...")
advance_phase(session_id, "challenge")

# 5. Challenge phase
challenge_claim(session_id, agent_id, contribution_id, "Challenge", "Reason")
advance_phase(session_id, "synthesis")

# 6. Synthesis phase
summarize(session_id)
add_agreement(session_id, "Agreement point")
advance_phase(session_id, "refine")

# 7. Refine phase (if needed)
share_reasoning(session_id, agent_id, "Updated view...")
advance_phase(session_id, "convergence")

# 8. Convergence phase
declare_consensus(session_id, "Final consensus statement")
advance_phase(session_id, "complete")

# 9. Review
get_state(session_id)
```

## Best Practices

1. **Always call the moderator** after each phase to manage transitions
2. **Use get_next_actions** to get phase-specific guidance
3. **Ensure all agents contribute** before advancing phases
4. **Track agreements/disagreements** explicitly using add_agreement/add_disagreement
5. **Detect stalemates** early and use moderator to request evidence
6. **Use prompt_agent** to guide agents when they're stuck
7. **Review session state** frequently with get_state or summarize
8. **Don't skip phases** - each phase serves a purpose in the consensus process

## Common Pitfalls

- **Skipping the moderator**: Leads to unmanaged sessions and stalemates
- **Not tracking agreements**: Makes it hard to identify convergence
- **Advancing phases too quickly**: Agents may not have full opportunity to contribute
- **Forgetting to call synthesizer**: Without synthesis, convergence is never detected
- **Not using phase guidance**: Results in disorganized sessions

## Getting Help

Use the `get_next_actions` tool at any point to get phase-specific guidance on what to do next.
