# Reviewer Routing

## Default (NEVER changes without explicit user request)

All review calls use the **Agent** tool with `subagent_type: "research-reviewer"`.

This is the default for ALL skills. No parameter, no config, no effort level changes this.

The `research-reviewer` subagent is defined in `agents/subagents/research-reviewer.yaml` and provides adversarial research review at NeurIPS/ICML level.

### Invariants

- `effort` and `difficulty` are orthogonal — they don't change reviewer backend
- `beast` mode may recommend deeper review but never requires a different backend
- The Agent tool is the canonical way to invoke reviewers in Kimi CLI

### Agent Call Format

```yaml
Agent:
  subagent_type: "research-reviewer"
  prompt: |
    [role + task + output schema]
    Read all listed files directly.
```

### Skills That Use the Research Reviewer

| Skill | Use case |
|-------|----------|
| `/skill:research-review` | Deep critique on paper drafts |
| `/skill:auto-review-loop` | Iterative adversarial review |
| `/skill:experiment-audit` | Line-by-line eval code audit |
| `/skill:proof-checker` | Deep mathematical reasoning |
| `/skill:rebuttal` | Stress test before submission |
| `/skill:idea-creator` | Idea evaluation depth |
| `/skill:research-lit` | Literature analysis depth |

### Multi-round Review

For follow-up rounds within the same review thread, use the Agent tool with `resume`:

```yaml
Agent:
  subagent_type: "research-reviewer"
  resume: "<agent_id from previous call>"
  prompt: |
    [follow-up task]
```

Save the `agent_id` returned from each Agent call for thread continuity.
