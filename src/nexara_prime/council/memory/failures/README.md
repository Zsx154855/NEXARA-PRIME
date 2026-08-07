# Council Memory — Failure Log

This directory stores persistent failure patterns — not transient errors,
but structural failures that the Council must remember across sessions.

Each entry is a JSON file named `<failure_id>-<timestamp>.json`:

```json
{
  "failure_id": "f-<uuid>",
  "timestamp": "ISO8601",
  "mission_id": "mis-<uuid>",
  "failure_type": "TEST_FAILURE|BUILD_FAILURE|RUNTIME_CRASH|GOVERNANCE_VIOLATION|SECURITY_BREACH",
  "severity": "R0|R1|R2|R3|R4",
  "root_cause": "classification",
  "resolution": "text or null",
  "preventive_measure": "what changed to prevent recurrence",
  "is_pattern": true
}
```

Patterns (is_pattern=true) are loaded into the session memory kernel.
Transient errors (is_pattern=false) are logged but not injected.
