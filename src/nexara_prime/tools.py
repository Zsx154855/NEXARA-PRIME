from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
import sys
import time
from pathlib import Path
from typing import Any

from .db import SQLiteStore
from .evidence import EvidenceStore
from .events import EventBus
from .governance import ApprovalEngine, PolicyEngine
from .models import ApprovalStatus, RiskLevel, ToolInvocation, new_id
from .models import now_iso
from .sandbox_v2 import MacOSSandboxBackend, ProcessConstrainedBackend, SandboxInvocation
from .security_audit import SecurityAuditLedger


class ToolRuntime:
    """Bounded local tool runtime with receipts, evidence and idempotent invocations."""

    MAX_READ_BYTES = 100_000
    MAX_OUTPUT_BYTES = 10_000
    MAX_WRITE_BYTES = 500_000
    DEFAULT_TIMEOUT_SECONDS = 5
    FORBIDDEN_COMMAND_PARTS = {
        "sudo", "rm", "rmdir", "unlink", "shred", "mkfs", "dd", "curl", "wget", "nc", "netcat",
        "ssh", "scp", "chmod", "chown", "mount", "umount", "launchctl", "osascript", "shutdown",
    }

    def __init__(self, store: SQLiteStore, events: EventBus, evidence: EvidenceStore, policy: PolicyEngine, approvals: ApprovalEngine, workspace_root: Path, report_root: Path, audit: SecurityAuditLedger | None = None):
        self.store = store
        self.events = events
        self.evidence = evidence
        self.policy = policy
        self.approvals = approvals
        self.workspace_root = workspace_root.resolve()
        self.report_root = report_root.resolve()
        self.audit = audit
        self.sandbox = MacOSSandboxBackend(str(self.workspace_root))
        self._fallback_sandbox: ProcessConstrainedBackend | None = None
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.report_root.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, root: Path, requested: str) -> Path:
        raw = Path(requested).expanduser()
        candidate = (root / raw).resolve() if not raw.is_absolute() else raw.resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise PermissionError(f"path_outside_allowed_root:{candidate}") from exc
        return candidate

    def _existing(self, idempotency_key: str | None) -> ToolInvocation | None:
        if not idempotency_key:
            return None
        raw = self.store.find_record("tool", "idempotency_key", idempotency_key)
        return ToolInvocation.model_validate(raw) if raw else None

    def invoke(
        self,
        mission_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        trace_id: str,
        safe_mode: bool = False,
        *,
        approval_id: str = "",
        actor_id: str = "",
        task_id: str = "",
        idempotency_key: str | None = None,
        timeout_seconds: int | None = None,
    ) -> ToolInvocation:
        existing = self._existing(idempotency_key)
        if existing:
            return existing
        risk = {
            "file_read": RiskLevel.R0,
            "read_file": RiskLevel.R0,
            "browser_readonly": RiskLevel.R1,
            "code_exec": RiskLevel.R1,
            "run_command_sandboxed": RiskLevel.R1,
            "file_write_report": RiskLevel.R2,
            "write_workspace_file": RiskLevel.R2,
        }.get(tool_name)
        if risk is None:
            raise KeyError(f"unknown_tool:{tool_name}")
        allowed, reason = self.policy.allows_tool(tool_name, risk, safe_mode)
        if not allowed:
            raise PermissionError(reason)

        # P0-2: Real Approval validation — never trust a bare boolean
        if self.policy.requires_approval(risk):
            if not approval_id:
                self._audit_denial(mission_id, task_id, tool_name, trace_id, actor_id, "missing_approval_id", risk)
                raise PermissionError("approval_required_for_tool: no approval_id provided")
            approval = self._validate_approval(
                approval_id,
                mission_id,
                tool_name,
                task_id,
                actor_id,
                trace_id,
                idempotency_key,
                arguments,
            )
            if not approval:
                self._audit_denial(mission_id, task_id, tool_name, trace_id, actor_id, "invalid_or_mismatched_approval", risk)
                raise PermissionError("approval_required_for_tool: invalid or expired approval")
        started = time.monotonic()
        status = "completed"
        result: dict[str, Any]
        failure: Exception | None = None
        try:
            if tool_name in {"file_read", "read_file"}:
                result = self._file_read(arguments)
            elif tool_name in {"file_write_report", "write_workspace_file"}:
                root = self.report_root if tool_name == "file_write_report" else self.workspace_root
                result = self._write_file(root, arguments)
            elif tool_name == "code_exec":
                result = self._code_exec(arguments, timeout_seconds or self.DEFAULT_TIMEOUT_SECONDS)
            elif tool_name == "run_command_sandboxed":
                result = self._run_command_sandboxed(arguments, timeout_seconds or self.DEFAULT_TIMEOUT_SECONDS)
            else:
                result = self._browser_readonly(arguments)
        except Exception as exc:
            status = "failed"
            failure = exc
            result = {"error": str(exc), "error_type": type(exc).__name__}
        invocation = ToolInvocation(
            invocation_id=new_id("tool"), mission_id=mission_id, tool_name=tool_name,
            arguments=arguments, result=result, risk_level=risk, status=status,
            duration_ms=int((time.monotonic() - started) * 1000), trace_id=trace_id,
            idempotency_key=idempotency_key,
            rollback_point={"kind": "filesystem_snapshot_placeholder", "reversible": tool_name in {"file_write_report", "write_workspace_file"}},
            compensation={"action": "restore_previous_content", "implemented": False},
        )
        self.store.save_record(invocation.invocation_id, "tool", invocation.model_dump(mode="json"), invocation.created_at, mission_id)
        event = self.events.publish(
            "tool.invoked", mission_id, "mission", "tool_runtime", trace_id,
            {"invocation_id": invocation.invocation_id, "tool": tool_name, "status": status, "idempotency_key": idempotency_key},
            idempotency_key=f"tool-event:{idempotency_key}" if idempotency_key else None,
        )
        evidence = self.evidence.add(
            mission_id, "execution_receipt", f"Tool receipt: {tool_name}", invocation.model_dump_json(), trace_id,
            event.event_id, task_id=task_id, tool_invocation_id=invocation.invocation_id,
            actor="tool_runtime", source="tool_runtime", verification_status="verified",
            idempotency_key=f"tool-evidence:{idempotency_key}" if idempotency_key else None,
        )
        invocation.receipt_evidence_id = evidence.evidence_id
        self.store.save_record(invocation.invocation_id, "tool", invocation.model_dump(mode="json"), invocation.created_at, mission_id)
        self._audit(
            event_type="tool.invoked",
            mission_id=mission_id,
            task_id=task_id,
            action=tool_name,
            decision="allowed" if status == "completed" else "failed",
            risk_level=risk,
            trace_id=trace_id,
            actor_id=actor_id or "tool_runtime",
            metadata={"invocation_id": invocation.invocation_id, "status": status},
        )
        if status == "failed":
            if failure is not None and isinstance(failure, (PermissionError, FileNotFoundError, ValueError)):
                raise failure
            raise RuntimeError(result.get("error", "tool_failed"))
        return invocation

    def _file_read(self, arguments: dict[str, Any]) -> dict[str, Any]:
        requested = str(arguments.get("path", "."))
        path = self._safe_path(self.workspace_root, requested)
        if path.is_dir():
            entries = []
            for item in sorted(path.rglob("*")):
                if item.is_file() and len(entries) < 100:
                    entries.append({"path": str(item.relative_to(self.workspace_root)), "bytes": item.stat().st_size})
            return {"path": requested, "directory": True, "entries": entries}
        if not path.exists():
            raise FileNotFoundError(path)
        content = path.read_text(encoding="utf-8", errors="replace")[: self.MAX_READ_BYTES]
        return {"path": requested, "directory": False, "content": content, "bytes": path.stat().st_size, "truncated": path.stat().st_size > self.MAX_READ_BYTES}

    def _write_file(self, root: Path, arguments: dict[str, Any]) -> dict[str, Any]:
        relative = str(arguments.get("path", "mission-report.md"))
        path = self._safe_path(root, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        content = str(arguments.get("content", ""))
        encoded = content.encode("utf-8")
        if len(encoded) > self.MAX_WRITE_BYTES:
            raise ValueError("write_payload_too_large")
        previous = path.read_bytes() if path.exists() else b""
        replayed = previous == encoded
        if not replayed:
            path.write_bytes(encoded)
        return {
            "path": str(path), "bytes": len(encoded), "sha256": hashlib.sha256(encoded).hexdigest(),
            "previous_sha256": hashlib.sha256(previous).hexdigest() if previous else None,
            "rollback_available": bool(previous), "root": str(root),
            "replayed": replayed,
        }

    def _code_exec(self, arguments: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
        code = str(arguments.get("code", "print('nexara-prime local execution check')"))
        if len(code) > 4_000:
            raise ValueError("code_payload_too_large")
        forbidden = ("os.remove", "os.unlink", "shutil.rmtree", "subprocess", "socket", "requests", "httpx", "open('/", "open(\"/", "os.system", "eval(")
        if any(token in code for token in forbidden):
            raise PermissionError("code_policy_rejected")
        argv = [os.path.realpath(sys.executable), "-I", "-c", code]
        receipt = self._sandbox_execute(argv, timeout_seconds)
        return {"returncode": receipt.exit_code, "stdout": receipt.stdout, "stderr": receipt.stderr, "truncated": len(receipt.stdout) >= self.MAX_OUTPUT_BYTES or len(receipt.stderr) >= self.MAX_OUTPUT_BYTES}

    def _run_command_sandboxed(self, arguments: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
        raw = arguments.get("command", [])
        command = shlex.split(raw) if isinstance(raw, str) else [str(part) for part in raw]
        if not command:
            raise ValueError("command_must_not_be_empty")
        lowered = [part.lower() for part in command]
        if any(part in self.FORBIDDEN_COMMAND_PARTS for part in lowered):
            raise PermissionError("command_policy_rejected")
        joined = " ".join(lowered)
        if any(token in joined for token in ("git push", "git merge", "git tag", "deploy", "|", ";", "&&", ">", "<", "`", "$()")):
            raise PermissionError("external_or_shell_command_rejected")
        allowed_executables = {"python", "python3", "python3.12", "git", "ls", "pwd", "find"}
        if Path(command[0]).name not in allowed_executables:
            raise PermissionError("executable_not_allowlisted")
        executable = command[0] if os.path.isabs(command[0]) else shutil.which(command[0])
        if executable:
            command[0] = os.path.realpath(executable)
        receipt = self._sandbox_execute(command, timeout_seconds)
        return {"command": command, "returncode": receipt.exit_code, "stdout": receipt.stdout, "stderr": receipt.stderr, "truncated": len(receipt.stdout) >= self.MAX_OUTPUT_BYTES or len(receipt.stderr) >= self.MAX_OUTPUT_BYTES}

    def _sandbox_execute(self, argv: list[str], timeout_seconds: int):
        allowed_dirs = [str(self.workspace_root), str(Path(sys.prefix).resolve()), str(Path(sys.base_prefix).resolve())]
        env = {
            "PATH": os.environ.get("PATH", ""),
            "NEXARA_ALLOWED_DIRS": ":".join(dict.fromkeys(allowed_dirs)),
        }
        receipt = self.sandbox.execute(SandboxInvocation(
            argv=argv,
            cwd=str(self.workspace_root),
            env=env,
            timeout=timeout_seconds,
            max_output_bytes=self.MAX_OUTPUT_BYTES,
            workspace_root=str(self.workspace_root),
        ))
        # posix_spawn failure is now handled in MacOSSandboxBackend
        # by properly including Python.app in the sandbox profile
        if receipt.timed_out:
            raise RuntimeError("tool_timeout")
        if receipt.error:
            raise PermissionError(f"os_sandbox_unavailable:{receipt.error}")
        return receipt

    def _browser_readonly(self, arguments: dict[str, Any]) -> dict[str, Any]:
        url = str(arguments.get("url", ""))
        if url.startswith("file://"):
            path = self._safe_path(self.workspace_root, url[7:])
            return {"url": url, "mode": "local_read_only", "content": path.read_text(encoding="utf-8", errors="replace")[: self.MAX_READ_BYTES]}
        if url.startswith(("http://", "https://")):
            return {"url": url, "mode": "read_only", "status": "blocked_by_default", "reason": "external_network_disabled_in_local_runtime"}
        raise ValueError("browser_url_must_be_http_or_file")

    def _validate_approval(
        self,
        approval_id: str,
        mission_id: str,
        tool_name: str,
        task_id: str,
        actor_id: str,
        trace_id: str,
        idempotency_key: str | None,
        arguments: dict[str, Any],
    ) -> bool:
        """P0-2: Validate real Approval from persistent store. Never trust parameters alone."""
        try:
            approval = self.approvals.get(approval_id)
        except ValueError:
            return False
        if not approval:
            return False
        if approval.mission_id != mission_id:
            return False
        if not actor_id:
            return False
        if approval.action != tool_name:
            return False
        if approval.executor_id and approval.executor_id != actor_id:
            return False
        if approval.status not in {
            ApprovalStatus.APPROVED,
            ApprovalStatus.CONSUMED,
        }:
            return False
        if approval.status == ApprovalStatus.APPROVED and approval.expires_at:
            from datetime import datetime, timezone

            try:
                if datetime.fromisoformat(approval.expires_at) <= datetime.now(
                    timezone.utc
                ):
                    return False
            except (ValueError, TypeError):
                pass
        use_id = (
            idempotency_key.strip()
            if idempotency_key and idempotency_key.strip()
            else task_id.strip() or f"tool:{tool_name}:{trace_id}"
        )
        claim = self._claim_approved_action(
            approval.approval_id,
            mission_id,
            tool_name,
            arguments,
            actor_id,
            use_id,
            idempotency_key,
            allow_create=approval.status == ApprovalStatus.APPROVED,
        )
        if approval.status == ApprovalStatus.CONSUMED:
            return claim and self.approvals.consumption_matches(
                approval,
                actor_id=actor_id,
                use_id=use_id,
            )
        # Scope check
        if approval.approval_scope == "single_action":
            if not self.approvals.consume_single_action(
                approval.approval_id,
                actor_id=actor_id,
                trace_id=trace_id,
                use_id=use_id,
            ):
                return False
        return True

    def _claim_approved_action(
        self,
        approval_id: str,
        mission_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        actor_id: str,
        use_id: str,
        idempotency_key: str | None,
        *,
        allow_create: bool,
    ) -> bool:
        """Durably bind one approval use to one exact tool request.

        The claim is written before approval consumption and before the side
        effect.  A restart may replay only the same approval, actor, use id,
        tool, and canonical arguments.
        """
        if not idempotency_key:
            return allow_create
        digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:20]
        record_id = f"toolclaim_{digest}"
        canonical_arguments = json.dumps(
            arguments, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        payload = {
            "approval_id": approval_id,
            "mission_id": mission_id,
            "tool_name": tool_name,
            "arguments_sha256": hashlib.sha256(
                canonical_arguments.encode("utf-8")
            ).hexdigest(),
            "actor_id": actor_id,
            "use_id": use_id,
            "idempotency_key": idempotency_key,
        }
        if allow_create:
            created_at = now_iso()
            if self.store.save_record_if_absent(
                record_id, "tool_claim", payload, created_at, mission_id
            ):
                return True
        existing = self.store.get_record_envelope(record_id)
        return bool(
            existing
            and existing.get("record_type") == "tool_claim"
            and existing.get("mission_id") == mission_id
            and existing.get("payload") == payload
        )

    def _audit_denial(self, mission_id: str, task_id: str, tool_name: str, trace_id: str, actor_id: str, reason: str, risk: RiskLevel) -> None:
        self._audit("tool.authorization_denied", mission_id, task_id, tool_name, "denied", risk, trace_id, actor_id or "unknown", {"reason": reason})

    def _audit(self, event_type: str, mission_id: str, task_id: str, action: str, decision: str, risk_level: RiskLevel, trace_id: str, actor_id: str, metadata: dict[str, Any]) -> None:
        if not self.audit:
            return
        actor_type = "agent" if actor_id not in {"human", "runtime", "tool_runtime", "unknown"} else "system"
        self.audit.record(
            event_type=event_type,
            actor_id=actor_id,
            actor_type=actor_type,
            mission_id=mission_id,
            task_id=task_id,
            action=action,
            decision=decision,
            risk_level=risk_level.value,
            trace_id=trace_id,
            metadata=metadata,
        )

    def list_invocations(self, mission_id: str | None = None) -> list[dict]:
        return self.store.list_records("tool", mission_id)
