# Council Memory — Evidence Archive

This directory stores mission evidence indexed by mission_id.
Each mission creates a subdirectory: `memory/evidence/<mission_id>/`

Contains:
- `execution_evidence.json` — tool invocations, outputs, exit codes
- `receipt.json` — BUILD_RECEIPT or EXECUTION_RECEIPT
- `risk_report.json` — H-RED findings
- `verification_report.json` — H-JUDGE verification
- `manifest.json` — file listing with SHA256 hashes

Evidence is immutable once committed. No deletion permitted.
