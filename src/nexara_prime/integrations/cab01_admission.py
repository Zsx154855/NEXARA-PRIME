"""CAB-01: validate durable, scoped NEXARA approval before OpenMausBot I/O.

This is a trusted *host-side* adapter, not an authentication server or OS
sandbox. The worker/model process must not hold the host's SQLite write access,
OpenMausBot CLI credentials, or the ability to instantiate a privileged host.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from ..models import ApprovalStatus, RiskLevel, WorkContract
from ..kernel_boundary import KernelBoundaryViolation, KernelExecutionGuard


class CAB01AdmissionDenied(PermissionError):
    """The authoritative store/policy does not permit this external action."""


def _digest(data: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _future(iso: str | None) -> bool:
    if not iso:
        return False
    try:
        value = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return value.tzinfo is not None and value > datetime.now(timezone.utc)
    except (TypeError, ValueError):
        return False


class CAB01TrustedAdmission:
    """Resolve real SQLiteStore envelopes and ApprovalEngine decision events.

    Inputs identifying a mission are lookup keys, never authority. The trusted
    host supplies the store, approved workspace root, executor identity and
    independently verified zero-cost engine set. This class cannot authenticate
    an OS user or determine provider billing by itself.
    """

    def __init__(self, store: Any, approvals: Any, policy: Any, *,
                 workspace_root: Path, execution_identity: str,
                 verified_zero_cost_engines: frozenset[str],
                 trusted_deciders: frozenset[str], guard: KernelExecutionGuard):
        if (not isinstance(workspace_root, Path) or not workspace_root.is_absolute()
            or not workspace_root.is_dir() or workspace_root.is_symlink()
            or not execution_identity or not trusted_deciders
            or not isinstance(guard, KernelExecutionGuard)):
            raise CAB01AdmissionDenied("invalid_host_authority_config")
        self.store = store
        self.approvals = approvals
        self.policy = policy
        self.workspace_root = workspace_root.resolve(strict=True)
        self.execution_identity = execution_identity
        self.verified_zero_cost_engines = verified_zero_cost_engines
        self.trusted_deciders = trusted_deciders
        self.guard = guard

    def authorize(self, mission_id: str, bot_id: str, thread_id: str,
                  objective: str) -> WorkContract:
        """Re-evaluate on every initial dispatch and any retry or resume."""
        if not all(isinstance(s, str) and s.strip()
                   for s in (mission_id, bot_id, thread_id, objective)):
            raise CAB01AdmissionDenied("invalid_dispatch_identity")
        # The existing immutable envelope API checks hashes, identity and origin.
        # A caller-supplied WorkContract or admitted dataclass is never accepted.
        contracts = self.store.list_record_envelopes("work_contract", mission_id)
        if not contracts:
            raise CAB01AdmissionDenied("missing_durable_work_contract")
        try:
            versions = [(WorkContract.model_validate(row["payload"]), row) for row in contracts]
        except (TypeError, ValueError, KeyError) as exc:
            raise CAB01AdmissionDenied("invalid_durable_work_contract") from exc
        latest_version = max(item.version for item, _ in versions)
        latest = [(contract, row) for contract, row in versions if contract.version == latest_version]
        if len(latest) != 1:
            raise CAB01AdmissionDenied("ambiguous_latest_contract")
        contract, record = latest[0]
        if (record.get("record_id") != contract.contract_id
            or record.get("mission_id") != mission_id
            or record.get("record_type") != "work_contract"
            or record.get("origin_sha256") != record.get("integrity_sha256")
            or contract.mission_id != mission_id
            or contract.status != "approved" or not contract.approved_at
            or not _future(contract.expires_at)):
            raise CAB01AdmissionDenied("work_contract_not_current")
        proposal_id = contract.provenance
        if not proposal_id or not contract.project_id:
            raise CAB01AdmissionDenied("missing_cognitive_provenance")
        goal = self.store.get_record_envelope(proposal_id)
        if (not goal or goal.get("record_id") != proposal_id
            or goal.get("record_type") != "cognitive_goal_proposal_v1"
            or goal.get("mission_id") != contract.project_id
            or goal.get("origin_sha256") != goal.get("integrity_sha256")):
            raise CAB01AdmissionDenied("unverified_cognitive_goal")
        payload = goal["payload"]
        if (payload.get("proposal_id") != proposal_id
            or payload.get("project_id") != contract.project_id
            or payload.get("status") not in {"HYPOTHESIS", "EVIDENCE_BACKED"}):
            raise CAB01AdmissionDenied("invalid_cognitive_goal")
        if (contract.objective != objective or contract.execution_backend != "openmausbot"
            or contract.execution_bot_id != bot_id
            or contract.execution_thread_id != thread_id
            or contract.execution_identity != self.execution_identity
            or "openmausbot.run" not in contract.allowed_actions):
            raise CAB01AdmissionDenied("execution_scope_mismatch")
        if contract.risk_level == RiskLevel.R4:
            raise CAB01AdmissionDenied("risk_level_forbidden")
        allowed, _ = self.policy.allows_tool("openmausbot.run", contract.risk_level)
        if not allowed:
            raise CAB01AdmissionDenied("existing_policy_denied")
        # The model's declaration that a provider is free is not a price fact.
        # Unknown engines (including configured Claude/Grok/DeepSeek) fail closed.
        if (type(contract.cost_limit) not in {float, int}
            or contract.cost_limit != 0
            or not contract.execution_engine
            or contract.execution_engine not in self.verified_zero_cost_engines):
            raise CAB01AdmissionDenied("model_budget_not_verified")
        path = Path(contract.authorized_workspace or "")
        if not path.is_absolute() or path.is_symlink():
            raise CAB01AdmissionDenied("workspace_scope_invalid")
        try:
            resolved = path.resolve(strict=True)
            resolved.relative_to(self.workspace_root)
        except (ValueError, OSError) as exc:
            raise CAB01AdmissionDenied("workspace_outside_authorized_root") from exc
        if resolved != path or not resolved.is_dir():
            raise CAB01AdmissionDenied("workspace_scope_invalid")
        # ApprovalEngine.list/get cross-check original request and decision
        # events, not only writable 'approved' strings in a JSON model.
        approval_hash = _digest(contract.model_dump(mode="json"))
        candidates = []
        try:
            for raw in self.approvals.list(mission_id):
                if raw.get("proposal_sha256") == approval_hash:
                    candidates.append(self.approvals.get(raw["approval_id"]))
        except (ValueError, KeyError, TypeError) as exc:
            raise CAB01AdmissionDenied("approval_integrity_invalid") from exc
        if len(candidates) != 1 or candidates[0] is None:
            raise CAB01AdmissionDenied("missing_unique_trusted_approval")
        approval = candidates[0]
        if (approval.mission_id != mission_id
            or approval.status != ApprovalStatus.APPROVED
            or approval.decided_by not in self.trusted_deciders
            or approval.approval_scope != "mission"
            or approval.action != "openmausbot.run"
            or approval.executor_id != self.execution_identity
            or approval.risk_level != contract.risk_level
            or approval.estimated_cost != 0
            or str(resolved) not in approval.affected_resources
            or not approval.external_effect
            or not _future(approval.expires_at)):
            raise CAB01AdmissionDenied("approval_scope_invalid_or_expired")
        # The existing Kernel guard is an additional admitted-work check, NOT
        # an authority oracle: its in-process dataclass can be constructed by
        # a caller, so the durable approval validation above remains mandatory.
        try:
            admission = self.guard.assert_admitted(mission_id)
            admission.assert_complete()
        except KernelBoundaryViolation as exc:
            raise CAB01AdmissionDenied("kernel_admission_required") from exc
        if (admission.metadata.get("contract_id") != contract.contract_id
            or admission.metadata.get("contract_version") != contract.version):
            raise CAB01AdmissionDenied("kernel_contract_binding_invalid")
        # No second approval store: revocation is an append-only mission event.
        # A revoked approval cannot authorize new retries or new effects.
        for event in self.store.list_events(mission_id):
            if (event.get("event_type") in {"approval.revoked", "cab.contract.revoked"}
                and event.get("payload", {}).get("approval_id") == approval.approval_id):
                raise CAB01AdmissionDenied("authorization_revoked")
        return contract
