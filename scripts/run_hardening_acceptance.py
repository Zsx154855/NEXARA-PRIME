#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from nexara_prime.config import Settings
from nexara_prime.runtime import NexaraRuntime


def run_command(args: list[str], root: Path) -> dict:
    result = subprocess.run(args, cwd=root, capture_output=True, text=True, check=False)
    return {"command": args, "returncode": result.returncode, "stdout": result.stdout[-8_000:], "stderr": result.stderr[-8_000:]}


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    output = root / "reports" / "production_hardening"
    mission_reports = output / "mission_reports"
    output.mkdir(parents=True, exist_ok=True)
    mission_reports.mkdir(parents=True, exist_ok=True)
    source = root / "workspace" / "sample-project"
    if not source.is_dir():
        raise SystemExit(f"real_source_directory_missing:{source}")
    settings = Settings(root / "runtime" / "hardening_acceptance.db", root / "workspace", mission_reports, "mock", True, "127.0.0.1", 8765)
    identity = {
        "pwd": str(root),
        "git_root": run_command(["git", "rev-parse", "--show-toplevel"], root),
        "remote": run_command(["git", "remote", "-v"], root),
        "branch": run_command(["git", "branch", "--show-current"], root),
        "status": run_command(["git", "status", "--short"], root),
        "recent_commit": run_command(["git", "log", "-1", "--oneline"], root),
        "project_marker": (root / "pyproject.toml").exists() and (root / "src" / "nexara_prime").is_dir(),
        "independent_project": root.name == "NEXARA-PRIME" and not (root / "AgentsOS").exists(),
    }
    identity["gate"] = "PASS" if identity["git_root"]["stdout"].strip() == str(root) and identity["branch"]["stdout"].strip() == "main" and identity["project_marker"] and identity["independent_project"] else "PARTIAL"
    (output / "repo_identity_gate.json").write_text(json.dumps(identity, ensure_ascii=False, indent=2), encoding="utf-8")

    runtime = NexaraRuntime(settings)
    recovery_before = runtime.recover().__dict__
    mission = runtime.create_mission("Read the real project materials and generate a verified project health report", str(source))
    planned = runtime.plan_mission(mission.mission_id)
    approval = None
    if planned.pending_approval_id:
        approval = runtime.approvals.get(planned.pending_approval_id)
        runtime.approve_mission(mission.mission_id, decision="approve_once", note="Approved for this bounded local acceptance mission.")
        approval = runtime.approvals.get(planned.pending_approval_id)
    completed = runtime.run_mission(mission.mission_id)
    evidence = runtime.evidence.list(mission.mission_id)
    evidence_check = runtime.evidence.verify_all(mission.mission_id)
    candidates = runtime.memory.candidates(mission.mission_id)
    memory = runtime.memory.inspect(mission.mission_id)
    evaluations = runtime.evaluator.list(mission.mission_id)
    recovery_after = runtime.recover().__dict__
    mission_summary = {
        "mission_id": completed.mission_id,
        "state": completed.state.value,
        "source_dir": str(source),
        "planned_state": planned.state.value,
        "approval_id": approval.approval_id if approval else None,
        "approval_status": approval.status.value if approval else "not_required",
        "result": completed.result,
        "evidence_count": len(evidence),
        "evidence_verification": evidence_check,
        "memory_candidates": candidates,
        "memory_committed": memory,
        "evaluations": evaluations,
        "recovery_before": recovery_before,
        "recovery_after": recovery_after,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    (output / "acceptance_mission.json").write_text(json.dumps(mission_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "evidence_chain.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "recovery_verification.json").write_text(json.dumps({"before": recovery_before, "after": recovery_after, "idempotent_run": runtime.run_mission(mission.mission_id).state.value == "Completed"}, ensure_ascii=False, indent=2), encoding="utf-8")
    runtime.store.close()

    checks = {
        "identity_gate": identity["gate"],
        "mission_completed": completed.state.value == "Completed",
        "approval_recorded": approval is not None and approval.status.value == "approved",
        "evidence_hashes_valid": evidence_check["invalid"] == 0,
        "evaluation_passed": bool(completed.result.get("evaluation_passed")),
        "memory_patch_committed": bool(memory),
        "report_exists": Path(completed.result["report_path"]).exists(),
        "recovery_reported": recovery_after["checked"] >= recovery_before["checked"],
    }
    overall = "PASS" if checks["identity_gate"] == "PASS" and all(value is True for key, value in checks.items() if key != "identity_gate") else "PARTIAL"
    report = [
        "# NEXARA PRIME Production Runtime Hardening V1 Acceptance",
        "",
        f"- Overall: **{overall}**",
        f"- Mission: `{completed.mission_id}`",
        f"- Source: `{source}`",
        "",
        "## Gate checks",
        "",
        "```json",
        json.dumps(checks, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Boundary",
        "",
        "Deterministic mock provider was used. The mission read only the local sample project, requested human approval for the bounded report write, generated tool receipts and evidence, committed an evidence-backed memory patch, and verified the completed mission is idempotent.",
        "",
        "## Artifacts",
        "",
        "- `repo_identity_gate.json`",
        "- `acceptance_mission.json`",
        "- `evidence_chain.json`",
        "- `recovery_verification.json`",
        "- `mission_reports/`",
    ]
    (output / "hardening_acceptance_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps({"overall": overall, "mission_id": completed.mission_id, "checks": checks, "output": str(output)}, ensure_ascii=False, indent=2))
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
