# NEXARA-PRIME Skills

> steipete-agent-ops compliant: portable SKILL.md files that define agent capabilities.

## What

Each skill is a `SKILL.md` file with YAML frontmatter. Drop it in `skills/` and NEXARA auto-discovers it.
Skills are the **canonical source of truth** for agent capabilities — not enum values in code.

## SKILL.md Template

```markdown
---
name: skill-name
description: "Short trigger phrase optimized for routing"
risk_level: R0|R1|R2
tools: [tool1, tool2]
capabilities: [cap1, cap2]
version: "1.0.0"
---

# Skill: [Name]

## Purpose
What this skill enables the agent to do.

## Tools
List of tools this skill provides.

## Constraints
R0-R4 constraints specific to this skill.

## Extension Points
How this skill can be extended.
```

## Discovery

```bash
# List all loaded skills
nexara skills list

# Validate all skills (steipete-validate pattern)
nexara skills validate

# Sync skills across agents (steipete-sync pattern)
nexara skills sync --target claude-code
nexara skills sync --target codex
```

## Portability

Skills are plain markdown files:
- **No runtime dependency**: can be read by any agent platform
- **Version controlled**: git-tracked, diffable, reviewable
- **Cross-platform**: works with Claude Code, Codex, Cursor, Copilot
- **steipete-compliant**: follow the `agent-scripts` canonical source pattern

## Example: sovereign-agent.skill.md

```markdown
---
name: sovereign-agent
description: "Human-centered bounded auditable agent execution"
risk_level: R1
tools: [mission_create, mission_approve, evidence_write]
capabilities: [state_machine, writer_lease, audit_chain]
version: "1.0.0"
---

# Skill: Sovereign Agent

## Purpose
Execute missions with human sovereignty controls:
approval gates, pause, takeover, rollback, safe mode.

## Tools
- `mission_create`: Create a new mission from human intent
- `mission_approve`: Approve an R2+ action
- `evidence_write`: Write an evidence artifact

## Constraints
- R2+ actions require human approval
- R4 actions are never automatic
- Writer Lease enforces single-writer-per-resource
- All state transitions emit events + evidence

## Extension Points
- Add custom tools via extensions/ directory
- Register new capabilities via capabilities/ directory
```
