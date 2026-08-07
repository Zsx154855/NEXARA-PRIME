# Council Memory — Decision Ledger

This directory stores immutable council decisions. Each decision is a
JSON file named `<decision_id>-<timestamp>.json` with the following schema:

```json
{
  "decision_id": "d-<uuid>",
  "timestamp": "ISO8601",
  "mission_id": "mis-<uuid>",
  "decision_type": "APPROVE|REJECT|DEFER|AMEND",
  "proposer": "agent_id",
  "voters": {"agent_id": "APPROVE|REJECT|ABSTAIN"},
  "result": "PASSED|REJECTED|TIED|VETOED",
  "rationale": "text",
  "nsec_reference": "Article X",
  "evidence_refs": ["ev-1", "ev-2"]
}
```

Rules:
- Once written, never modified
- Vetoed decisions are preserved (not deleted)
- All decisions link to their parent mission_id
