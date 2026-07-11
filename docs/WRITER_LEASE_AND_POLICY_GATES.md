# Writer Lease Protocol & R0-R4 Policy Gates

> NEXARA-PRIME's core security primitives for human-centered sovereign agent execution.

---

## Writer Lease Protocol

### Problem

Multiple agents or processes may attempt to modify the same resource (mission, memory, evidence) concurrently. Without coordination, this produces race conditions, data corruption, and untraceable conflicts.

### Solution

**Writer Lease** is a cooperative locking protocol enforced at the database level. Before any write operation, the writer must acquire a lease on the target resource. Only one writer holds an active lease per resource at any time.

### Protocol

```
ACQUIRE → WRITE → RELEASE
   │                   │
   └── TTL expires ────┘ (auto-release)
```

1. **Acquire**: Writer requests a lease on `resource_id`, providing `writer` identity, `trace_id`, and `ttl_seconds` (default 300s / 5 minutes).
2. **Conflict Check**: If an active lease (not expired) exists for the same resource with a different writer → `RuntimeError("writer_lease_conflict:{resource_id}:{current_writer}")` is raised.
3. **Write**: Writer performs operations. Lease is valid for the TTL duration.
4. **Release**: Writer explicitly releases the lease, or it expires automatically.
5. **Event**: Every lease acquisition and release publishes a `governance.writer_lease.acquired` / `governance.writer_lease.released` event.

### Implementation

```python
# src/nexara_prime/governance.py

class WriterLeaseManager:
    def acquire(self, resource_id, writer, trace_id, ttl_seconds=300) -> WriterLease
    def release(self, lease_id, writer, trace_id) -> None
```

### Guarantees

| Guarantee | Mechanism |
|-----------|-----------|
| **Single writer** | Active lease check before acquisition → RuntimeError on conflict |
| **Dead writer recovery** | TTL-based expiry (default 300s) — stale leases auto-release |
| **Auditability** | Every lease operation publishes an event |
| **Durability** | Leases stored in SQLite, survive process restart |

### Current Limitations

- Lease TTL is fixed per acquisition, not dynamically extended
- No lease renewal / heartbeat mechanism (writer must release and re-acquire for long operations)
- Cross-process lease coordination relies on shared SQLite DB (not distributed)

---

## R0-R4 Policy Gates

### Risk Level Hierarchy

| Level | Name | Meaning | Examples | Auto-Approved? |
|-------|------|---------|----------|---------------|
| **R0** | Read-only | No side effects, no writes | `file_read`, `browser_readonly`, status queries | ✅ Yes |
| **R1** | Safe local write | Writes within project boundary, no network | Local report generation, evidence artifact creation | ✅ Yes |
| **R2** | Consequential | Modifies shared state, affects other missions | Mission state change, memory patch, tool invocation | ❌ Approval Required |
| **R3** | External effect | Network access, external service call | API call, webhook, connector invocation | ❌ Double Approval Required |
| **R4** | Blocked | Never automatic | Shell execution, arbitrary command, system modification | ❌ **NEVER** automatic |

### Policy Engine Rules

```python
# src/nexara_prime/governance.py

class PolicyEngine:
    APPROVAL_LEVELS = {R2, R3, R4}

    def requires_approval(self, risk_level: RiskLevel) -> bool:
        return risk_level in {R2, R3, R4}

    def allows_tool(self, tool_name, risk_level, safe_mode=False):
        # Safe mode: only read-only tools
        if safe_mode and tool_name not in {"file_read", "browser_readonly"}:
            return False, "safe_mode_allows_read_only_tools"

        # R4: NEVER automatic
        if risk_level == R4:
            return False, "R4_actions_are_never_automatic"

        # Shell/command execution: always requires sandboxed tool
        if tool_name in {"shell", "run_command"}:
            return False, "command_execution_requires_sandboxed_tool"

        return True, "policy_allows"
```

### Approval Flow

```
Action Proposed
    ↓
Risk Classification (R0-R4)
    ↓
R0/R1? → Execute immediately
    ↓
R2?    → Create ApprovalRequest → Wait for human approval → Execute / Deny
    ↓
R3?    → Create ApprovalRequest → Wait for TWO human approvals → Execute / Deny
    ↓
R4?    → BLOCKED — never automatic
```

### Human Sovereignty Controls

| Control | Mechanism | Trigger |
|---------|-----------|---------|
| **Approve** | `ApprovalEngine.approve(approval_id)` | Human reviews and approves R2+ action |
| **Deny** | `ApprovalEngine.deny(approval_id)` | Human rejects action |
| **Pause** | MissionState → PAUSED | Human pauses mission mid-execution |
| **Takeover** | Writer Lease transfer | Human takes control of resource from agent |
| **Rollback** | State machine → ROLLED_BACK | Human reverts mission to any prior state |
| **Safe Mode** | `safe_mode=True` → read-only tools only | Human activates emergency safe mode |

### Security Baseline (Verified)

```
Secret Leakage:   0
Approval Bypass:  0
Sandbox Escape:   0
Hash Mismatches:  0
Audit Chain:      intact
Network:          deny-by-default
Runtime:          macOS sandbox (OS_SANDBOX_CAPABLE)
```

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    HUMAN (Sovereign)                     │
│  Owns: approve, pause, takeover, rollback, safe-mode    │
└──────────────────────┬──────────────────────────────────┘
                       │ Intent
                       ▼
┌─────────────────────────────────────────────────────────┐
│              NEXARA-PRIME Kernel                         │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐  │
│  │ Mission  │  │ Work     │  │ Policy Engine         │  │
│  │ Compiler │→ │ Contract │→ │ R0-R4 Classification  │  │
│  └──────────┘  └──────────┘  └─────────┬────────────┘  │
│                                        │                 │
│                          ┌─────────────▼──────────────┐ │
│                          │ Approval Gate              │ │
│                          │ R2: 1 human ✓              │ │
│                          │ R3: 2 humans ✓✓            │ │
│                          │ R4: BLOCKED ✗              │ │
│                          └─────────────┬──────────────┘ │
│                                        │                 │
│  ┌──────────┐  ┌──────────┐  ┌────────▼─────────────┐  │
│  │ Writer   │  │ State    │  │ Tool Runtime           │  │
│  │ Lease    │←→│ Machine  │←→│ (sandboxed execution)  │  │
│  │ Manager  │  │ (14 states)│                          │  │
│  └──────────┘  └──────────┘  └───────────┬───────────┘  │
│                                          │               │
│  ┌──────────┐  ┌──────────┐  ┌───────────▼───────────┐  │
│  │ Evidence │  │ Memory   │  │ Audit Chain            │  │
│  │ Store    │  │ Kernel   │  │ (append-only, durable)  │  │
│  └──────────┘  └──────────┘  └────────────────────────┘  │
│                                                          │
│  Persistence: SQLite  ·  Events: EventBus  ·  Recovery  │
└─────────────────────────────────────────────────────────┘
```

---

## Integration with AgentsOS

NEXARA-PRIME is the **engine layer** of AgentsOS. Every mission, work contract, approval, and audit artifact flows through these primitives.

```
agentsos engine status       → check engine health
agentsos engine mission      → manage missions
agentsos engine security     → security audit and status
agentsos engine doctor       → repository health checks
```

---

> Document version: 1.0
> Last updated: 2026-07-12
> Verified against: NEXARA-PRIME src/nexara_prime/governance.py · models.py · runtime.py
