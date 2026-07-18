from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from .adaptive_runtime import AdaptiveRuntime as AdaptiveOrchestrator
from .capabilities import CapabilityRegistry
from .config import Settings
from .contract_engine import ContractEngine
from .db import SQLiteStore
from .evaluation import EvaluationEngine
from .evidence import EvidenceStore
from .events import EventBus
from .governance import ApprovalEngine, PolicyEngine, WriterLeaseManager
from .memory import MemoryKernel
from .mission_compiler import MissionCompiler
from .model_gateway import LocalModelProvider, ModelGateway, MockProvider, OpenAICompatibleProvider, ProviderUnavailable, UnavailableProvider
from .models import (
    Mission, MissionState, RiskLevel, AdaptiveMissionProfile,
    now_iso, new_id,
)
from .recovery import DurableRecovery
from .scheduler import AdaptiveScheduler
from .security_audit import SecurityAuditLedger
from .state_machine import MissionStateMachine
from .token_compiler import TokenCompiler
from .tools import ToolRuntime

# ── Runtime Closure v1: Governed Adapters ──
_ADAPTERS_INITIALIZED = False
_browser_adapter = None
_computer_use_adapter = None
_git_adapter = None
_message_adapter = None
_deployment_adapter = None
_rag_pipeline = None
_memory_layer_manager = None
_repair_loop = None
_program_loop = None
_adapters_lock = threading.Lock()

def _ensure_adapters(runtime):
    global _ADAPTERS_INITIALIZED, _browser_adapter, _computer_use_adapter
    global _git_adapter, _message_adapter, _deployment_adapter
    global _rag_pipeline, _memory_layer_manager, _repair_loop, _program_loop
    # Fast-path check (no lock needed for already-initialized same runtime)
    if _ADAPTERS_INITIALIZED and getattr(_ensure_adapters, '_last_runtime_id', None) == id(runtime):
        return
    with _adapters_lock:
        # Double-check under lock
        if _ADAPTERS_INITIALIZED and getattr(_ensure_adapters, '_last_runtime_id', None) == id(runtime):
            return
        _ensure_adapters._last_runtime_id = id(runtime)
        _ADAPTERS_INITIALIZED = False  # Force re-init for new runtime
        try:
    
            from .browser_adapter import GovernedBrowserAdapter, MockBrowserDriver
            _browser_adapter = GovernedBrowserAdapter(
                MockBrowserDriver(),
                evidence_store=runtime.evidence,
                approval_engine=runtime.approvals,
            )
        except ImportError:
            pass
        try:
            from .computer_use_adapter import GovernedComputerUseAdapter, MockComputerUseDriver
            _computer_use_adapter = GovernedComputerUseAdapter(
                MockComputerUseDriver(),
                evidence_store=runtime.evidence,
                approval_engine=runtime.approvals,
            )
        except ImportError:
            pass
        try:
            from .git_adapter import GovernedGitAdapter, MockGitDriver
            _git_adapter = GovernedGitAdapter(
                MockGitDriver(),
                evidence_store=runtime.evidence,
                approval_engine=runtime.approvals,
            )
        except ImportError:
            pass
        try:
            from .message_adapter import GovernedMessageAdapter, MockMessageProvider
            _message_adapter = GovernedMessageAdapter(
                MockMessageProvider(),
                evidence_store=runtime.evidence,
                approval_engine=runtime.approvals,
            )
        except ImportError:
            pass
        try:
            from .deployment_adapter import GovernedDeploymentAdapter, MockDeploymentDriver
            _deployment_adapter = GovernedDeploymentAdapter(
                MockDeploymentDriver(),
                evidence_store=runtime.evidence,
                approval_engine=runtime.approvals,
            )
        except ImportError:
            pass
        try:
            from .rag_pipeline import RAGPipeline, MockEmbedder
            _rag_pipeline = RAGPipeline(MockEmbedder())
        except ImportError:
            pass
        try:
            from .memory import MemoryLayerManager
            if _rag_pipeline:
                _memory_layer_manager = MemoryLayerManager(
                    runtime.memory, _rag_pipeline, enable_patch_review=True,
                )
            else:
                _memory_layer_manager = MemoryLayerManager(
                    runtime.memory, rag=None, enable_patch_review=True,
                )
        except ImportError:
            pass
        try:
            from .repair_loop import RepairLoop
            _repair_loop = RepairLoop(
                evidence_store=runtime.evidence,
                approval_engine=runtime.approvals,
            )
        except ImportError:
            pass
        try:
            from .program_loop import ProgramLoop, ProgramLoopConfig
            _program_loop = ProgramLoop(
                ProgramLoopConfig(max_cycles=0),
                store=runtime.store,
                events=runtime.events,
                evidence=runtime.evidence,
                scheduler=runtime.scheduler,
                runtime=runtime,
            )
        except ImportError:
            pass
    
        _ADAPTERS_INITIALIZED = True

# Adaptive Runtime imports (lazy — loaded on first use)
_ADAPTIVE_IMPORTS_DONE = False
_adaptive_triage = None
_adaptive_scheduler_v2 = None
_adaptive_capabilities_v2 = None
_adaptive_router = None
_adaptive_budgets = None
_adaptive_escalation = None
_adaptive_tokens_v2 = None

def _ensure_adaptive_imports():
    global _ADAPTIVE_IMPORTS_DONE, _adaptive_triage, _adaptive_scheduler_v2
    global _adaptive_capabilities_v2, _adaptive_router, _adaptive_budgets
    global _adaptive_escalation, _adaptive_tokens_v2
    if _ADAPTIVE_IMPORTS_DONE:
        return
    try:
        from .mission_triage import MissionTriageEngine
        _adaptive_triage = MissionTriageEngine()
    except ImportError:
        _adaptive_triage = None
    try:
        from .adaptive_scheduler import AdaptiveMultiAgentScheduler
        _adaptive_scheduler_v2 = AdaptiveMultiAgentScheduler()
    except ImportError:
        _adaptive_scheduler_v2 = None
    try:
        from .capability_registry_v2 import CapabilityRegistryV2
        _adaptive_capabilities_v2 = CapabilityRegistryV2()
    except ImportError:
        _adaptive_capabilities_v2 = None
    try:
        from .model_router import ModelRouter
        _adaptive_router = ModelRouter()
    except ImportError:
        _adaptive_router = None
    try:
        from .resource_budget import ResourceBudgetManager
        _adaptive_budgets = ResourceBudgetManager()
    except ImportError:
        _adaptive_budgets = None
    try:
        from .escalation import EscalationEngine
        _adaptive_escalation = EscalationEngine()
    except ImportError:
        _adaptive_escalation = None
    try:
        from .token_compiler_v2 import TokenCompilerV2
        _adaptive_tokens_v2 = TokenCompilerV2()
    except ImportError:
        _adaptive_tokens_v2 = None
    _ADAPTIVE_IMPORTS_DONE = True


class NexaraRuntime:
    """Application service coordinating the durable, bounded NEXARA kernel."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings.from_env()
        self.settings.ensure_dirs()
        self.store = SQLiteStore(self.settings.db_path)
        self.events = EventBus(self.store)
        self.audit = SecurityAuditLedger(self.store)
        self.evidence = EvidenceStore(self.store, self.events)
        self.memory = MemoryKernel(self.store, self.events)
        self.policy = PolicyEngine()
        self.approvals = ApprovalEngine(self.store, self.events)
        self.leases = WriterLeaseManager(self.store, self.events)
        self.capabilities = CapabilityRegistry()
        self.scheduler = AdaptiveScheduler(self.capabilities)
        self.compiler = MissionCompiler()
        self.contracts = ContractEngine()
        self.tokens = TokenCompiler()
        self.models = self._build_model_gateway()
        self.tools = ToolRuntime(self.store, self.events, self.evidence, self.policy, self.approvals, self.settings.workspace_root, self.settings.report_root, self.audit)
        self.evaluator = EvaluationEngine(self.store, self.events)
        self.state_machine = MissionStateMachine(self.events, self.evidence)
        self.recovery = DurableRecovery(self.store, self.events)

    # ── Adapter accessors ──

    @property
    def browser(self):
        _ensure_adapters(self)
        return _browser_adapter

    @property
    def computer_use(self):
        _ensure_adapters(self)
        return _computer_use_adapter

    @property
    def git(self):
        _ensure_adapters(self)
        return _git_adapter

    @property
    def messenger(self):
        _ensure_adapters(self)
        return _message_adapter

    @property
    def deployment(self):
        _ensure_adapters(self)
        return _deployment_adapter

    @property
    def rag(self):
        _ensure_adapters(self)
        return _rag_pipeline

    @property
    def memory_layers(self):
        _ensure_adapters(self)
        return _memory_layer_manager

    @property
    def repair(self):
        _ensure_adapters(self)
        return _repair_loop

    @property
    def program(self):
        _ensure_adapters(self)
        return _program_loop

    def _build_model_gateway(self) -> ModelGateway:
        provider_name = self.settings.model_provider.lower()
        if self.settings.mock_model:
            return ModelGateway(MockProvider(), fallback=None)
        if provider_name == "mock" and not self.settings.mock_model:
            self._provider_unavailable = True
            return ModelGateway(UnavailableProvider())
        if provider_name in {"openai", "openai_compatible"}:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                self._provider_unavailable = True
                return ModelGateway(UnavailableProvider())
            provider = OpenAICompatibleProvider(
                os.getenv("NEXARA_MODEL_ENDPOINT", "https://api.openai.com/v1"),
                model=os.getenv("NEXARA_MODEL_NAME", "gpt-4o-mini"),
                api_key=api_key,
            )
        elif provider_name == "local":
            endpoint = os.getenv("NEXARA_LOCAL_MODEL_ENDPOINT")
            if not endpoint:
                self._provider_unavailable = True
                return ModelGateway(UnavailableProvider())
            provider = LocalModelProvider(endpoint, os.getenv("NEXARA_MODEL_NAME", "local-model"))
        else:
            self._provider_unavailable = True
            return ModelGateway(UnavailableProvider())
        self._provider_unavailable = False
        return ModelGateway(provider, fallback=None)

    def _save_mission(self, mission: Mission) -> None:
        mission.updated_at = now_iso()
        self.store.save_record(mission.mission_id, "mission", mission.model_dump(mode="json"), mission.created_at, mission.mission_id)

    def _load_mission(self, mission_id: str) -> Mission:
        raw = self.store.get_record(mission_id)
        if not raw:
            raise KeyError(f"mission_not_found:{mission_id}")
        return Mission.model_validate(raw)

    def create_mission(self, objective: str, source_dir: str | None = None) -> Mission:
        spec = self.compiler.compile(objective, source_dir)
        mission = Mission(mission_id=spec.mission_id, spec=spec, trace_id=new_id("trace"))
        self._save_mission(mission)
        self.events.publish("mission.created", mission.mission_id, "mission", "human", mission.trace_id, {"title": spec.title, "risk_level": spec.risk_level.value}, idempotency_key=f"mission-created:{mission.mission_id}")
        self.audit.record(
            "mission.created", actor_id="human", actor_type="human", mission_id=mission.mission_id,
            action="create_mission", decision="allowed", risk_level=spec.risk_level.value,
            trace_id=mission.trace_id, metadata={"title": spec.title},
        )
        self.evidence.add(mission.mission_id, "mission_spec", "MissionSpec", spec.model_dump_json(indent=2), mission.trace_id, actor="compiler", source="mission_compiler", verification_status="verified", idempotency_key=f"mission-spec:{mission.mission_id}")
        return mission

    def get_mission(self, mission_id: str) -> Mission:
        return self._load_mission(mission_id)

    def list_missions(self) -> list[dict]:
        return self.store.list_records("mission")

    def _advance(self, mission: Mission, target: MissionState, actor: str) -> None:
        previous = mission.state
        self.state_machine.transition(mission, target, actor)
        self._save_mission(mission)
        self.audit.record(
            "mission.state_changed", actor_id=actor, actor_type="system", mission_id=mission.mission_id,
            action=f"{previous}->{target.value}", decision="allowed", risk_level=mission.spec.risk_level.value,
            trace_id=mission.trace_id, metadata={"from_state": previous, "to_state": target.value},
        )

    def plan_mission(self, mission_id: str) -> Mission:
        mission = self._load_mission(mission_id)
        if mission.state != MissionState.INTENT.value:
            return mission
        self._advance(mission, MissionState.CONTEXT, "nexara")
        if mission.spec.source_dir:
            try:
                root = Path(mission.spec.source_dir).resolve()
                workspace = self.settings.workspace_root.resolve()
                relative = str(root.relative_to(workspace)) if root != workspace else "."
                inventory = self.tools.invoke(mission.mission_id, "file_read", {"path": relative}, mission.trace_id, safe_mode=True, idempotency_key=f"{mission.mission_id}:context-inventory")
                context_summary = json.dumps(inventory.result, ensure_ascii=False)[:1_500]
                self.evidence.add(mission.mission_id, "context_snapshot", "Source inventory", context_summary, mission.trace_id, tool_invocation_id=inventory.invocation_id, actor="nexara", source="file_read", verification_status="verified", idempotency_key=f"{mission.mission_id}:context-evidence")
            except (ValueError, PermissionError, RuntimeError):
                context_summary = "Source directory recorded; runtime read skipped because it is outside the approved workspace root."
        else:
            context_summary = "No external source directory; task is bounded to the NEXARA workspace."
        self.recovery.checkpoint(mission.mission_id, "context_assembled", mission.trace_id, data={"summary": context_summary})
        self._advance(mission, MissionState.CONTRACT, "nexara")
        mission.contract = self.contracts.create(mission.spec)
        self._save_mission(mission)
        self.recovery.checkpoint(mission.mission_id, "contract_created", mission.trace_id, data={"contract_id": mission.contract.contract_id})
        self._advance(mission, MissionState.PLAN, "nexara")
        mission.assignments = self.scheduler.schedule(mission.spec)
        steps = [{"role": assignment.runtime_role.value, "persona": assignment.persona.value, "capabilities": assignment.loaded_capabilities} for assignment in mission.assignments]
        mission.plan = self._build_plan(mission, steps)
        self._save_mission(mission)
        self._advance(mission, MissionState.SIMULATION, "nexara")
        mission.plan.simulated = True
        self._save_mission(mission)
        self.recovery.checkpoint(mission.mission_id, "plan_simulated", mission.trace_id, data={"steps": len(mission.plan.steps)})
        # Every mission report write is R2, even when the surrounding objective
        # is low risk. The write itself therefore always requires human approval.
        if self.policy.requires_approval(RiskLevel.R2):
            approval = self.approvals.request(
                mission.mission_id, "file_write_report", RiskLevel.R2,
                "The mission will write one bounded report under the approved report root.",
                ["Creates or updates a local report file", "No external network or deletion"], mission.trace_id,
                affected_resources=[str(self.settings.report_root / mission.mission_id)],
                external_effect=False, reversible=True,
                rollback_plan={"kind": "restore_previous_report", "implemented": False},
                estimated_cost=0.0, approval_scope="single_action", executor_id="runtime",
            )
            self.audit.record(
                "approval.requested", actor_id="governance", actor_type="system", mission_id=mission.mission_id,
                action=approval.action, decision="pending", risk_level=approval.risk_level.value,
                trace_id=mission.trace_id, metadata={"approval_id": approval.approval_id},
            )
            mission.pending_approval_id = approval.approval_id
            self._advance(mission, MissionState.APPROVAL, "governance")
        else:
            self._advance(mission, MissionState.EXECUTION, "policy")
        return mission

    def _build_plan(self, mission: Mission, roles: list[dict]):
        from .models import MissionPlan, PlanStep, Persona, RuntimeRole
        steps = []
        for item in roles:
            role = RuntimeRole(item["role"])
            persona = Persona(item["persona"])
            steps.append(PlanStep(title=f"{role.value} stage", description=f"{role.value} contributes to the mission with bounded capabilities.", role=role, persona=persona, required_capabilities=item["capabilities"]))
        return MissionPlan(mission_id=mission.mission_id, steps=steps)

    def approve_mission(self, mission_id: str, approved: bool = True, actor: str = "human", note: str = "Approved for bounded local MVP execution.", decision: str | None = None, scope: str | None = None) -> Mission:
        mission = self._load_mission(mission_id)
        if not mission.pending_approval_id:
            raise ValueError("mission_has_no_pending_approval")
        decision_record = self.approvals.decide(mission.pending_approval_id, approved, actor, note, mission.trace_id, decision=decision, scope=scope)
        self.audit.record(
            "approval.decided", actor_id=actor, actor_type="human" if actor == "human" else "system",
            mission_id=mission.mission_id, action=decision_record.action,
            decision=decision_record.status.value, risk_level=decision_record.risk_level.value,
            trace_id=mission.trace_id, metadata={"approval_id": decision_record.approval_id, "decided_by": actor},
        )
        if decision_record.status.value == "approved":
            mission.contract = self.contracts.approve(mission.contract) if mission.contract else None
            self._advance(mission, MissionState.EXECUTION, actor)
        elif decision_record.status.value == "paused":
            mission.paused = True
            self._save_mission(mission)
        elif decision_record.status.value == "changes_requested":
            mission.result["approval_feedback"] = note
            self._save_mission(mission)
        else:
            self._advance(mission, MissionState.BLOCKED, actor)
        return mission

    def _checkpointed_model(self, mission: Mission, compiled, context: dict) -> tuple[str, str, int, int, float]:
        tk = f"{mission.mission_id}:model_tokens"
        p = mission.result.get(tk)
        if p and isinstance(p, dict) and int(p.get("input_tokens", 0)) > 0:
            return mission.result.get("model_text", ""), p.get("provider", "unknown"), int(p["input_tokens"]), int(p["output_tokens"]), float(p.get("cost_usd", 0.0))
        # Migrate the durable response written by the pre-convergence runtime.
        # This check must precede the provider call or a restart can duplicate
        # an already completed and billed model request.
        legacy_key = f"{mission.mission_id}:model-completion"
        legacy_envelope = self.store.find_record_envelope(
            "model_response", "idempotency_key", legacy_key
        )
        legacy = (
            legacy_envelope["payload"]
            if legacy_envelope
            and legacy_envelope.get("mission_id") == mission.mission_id
            else None
        )
        if legacy:
            required = {"text", "provider", "input_tokens", "output_tokens"}
            if not required.issubset(legacy):
                raise ValueError("legacy_model_response_invalid")
            migrated = {
                "input_tokens": int(legacy["input_tokens"]),
                "output_tokens": int(legacy["output_tokens"]),
                "cost_usd": float(legacy.get("cost_usd", 0.0)),
                "provider": str(legacy["provider"]),
            }
            mission.result[tk] = migrated
            mission.result["model_text"] = str(legacy["text"])
            mission.result["model_provider"] = migrated["provider"]
            self._clear_provider_unavailable(mission)
            self._save_mission(mission)
            return (
                mission.result["model_text"],
                migrated["provider"],
                migrated["input_tokens"],
                migrated["output_tokens"],
                migrated["cost_usd"],
            )
        model_response = self.models.complete(compiled.system, compiled.task, context, trace_id=mission.trace_id)
        mission.result[tk] = {"input_tokens": model_response.input_tokens, "output_tokens": model_response.output_tokens, "cost_usd": model_response.cost_usd, "provider": model_response.provider}
        mission.result["model_text"] = model_response.text
        mission.result["model_provider"] = model_response.provider
        self._clear_provider_unavailable(mission)
        self._save_mission(mission)
        self.recovery.checkpoint(mission.mission_id, "model_completed", mission.trace_id, data={"provider": model_response.provider})
        return model_response.text, model_response.provider, model_response.input_tokens, model_response.output_tokens, model_response.cost_usd

    def _clear_provider_unavailable(self, mission: Mission) -> None:
        """Clear only the transient provider failure state after real success."""
        recovery = mission.result.get("recovery")
        if isinstance(recovery, dict):
            recovery.pop("provider_unavailable", None)
            recovery.pop("retry_after_configured", None)
            if not recovery:
                mission.result.pop("recovery", None)
        if getattr(getattr(self.models, "provider", None), "name", None) != "unavailable":
            self._provider_unavailable = False

    def run_mission(self, mission_id: str) -> Mission:
        mission = self._load_mission(mission_id)
        if mission.state == MissionState.COMPLETED.value:
            return mission
        if mission.paused:
            return mission
        if mission.state == MissionState.APPROVAL.value:
            if mission.safe_mode:
                raise PermissionError("safe_mode_blocks_unapproved_mission")
            return mission
        _ADAPTIVE = {"Running", "Verifying", "Degraded"}
        if mission.state in _ADAPTIVE:
            raise ValueError(f"ADAPTIVE_RECOVERY_REQUIRED: {mission.state}")
        _DISPATCH = {
            MissionState.EXECUTION.value: self._execute_stage,
            MissionState.VERIFICATION.value: self._verify_stage,
            MissionState.EVIDENCE.value: self._commit_evidence_stage,
            MissionState.MEMORY_PATCH.value: self._update_memory_stage,
            MissionState.EVALUATION.value: self._evaluate_stage,
        }
        processor = _DISPATCH.get(mission.state)
        if processor is None:
            raise ValueError(f"mission_not_ready_to_run:{mission.state}")
        try:
            return processor(mission)
        except ProviderUnavailable:
            mission.result["recovery"] = {"provider_unavailable": True, "retry_after_configured": True}
            self._save_mission(mission)
            raise
        except Exception as exc:
            mission.result["error"] = str(exc)
            self._save_mission(mission)
            current = MissionState(mission.state)
            if current not in {MissionState.COMPLETED, MissionState.ROLLED_BACK, MissionState.FAILED}:
                try:
                    self._advance(mission, MissionState.FAILED, "runtime")
                except ValueError:
                    pass
            raise

    def _execute_stage(self, mission: Mission) -> Mission:
        model_key = f"{mission.mission_id}:model_tokens"
        persisted = mission.result.get(model_key)
        if persisted and isinstance(persisted, dict):
            mt = int(persisted.get("input_tokens", 0))
            ot = int(persisted.get("output_tokens", 0))
            c = float(persisted.get("cost_usd", 0.0))
            model_text = mission.result.get("model_text", "")
            provider = persisted.get("provider", "unknown")
        else:
            context = {"source_dir": mission.spec.source_dir or "workspace", "roles": [a.persona.value for a in mission.assignments]}
            compiled = self.tokens.compile(mission.spec, [cap for a in mission.assignments for cap in a.loaded_capabilities], ["MissionSpec", "WorkContract", "MissionPlan"], [e["evidence_id"] for e in self.evidence.list(mission.mission_id)], json.dumps(context))
            model_text, provider, mt, ot, c = self._checkpointed_model(mission, compiled, context)
            mission.result[model_key] = {"input_tokens": mt, "output_tokens": ot, "cost_usd": c, "provider": provider}
            mission.result["model_text"] = model_text
        code = self.tools.invoke(mission.mission_id, "code_exec", {"code": "print('nexara-prime local execution check')"}, mission.trace_id, safe_mode=mission.safe_mode, actor_id="runtime", task_id=mission.mission_id, idempotency_key=f"{mission.mission_id}:code-check")
        self.recovery.checkpoint(mission.mission_id, "tools_checked", mission.trace_id, data={"invocation_id": code.invocation_id})
        report = self._render_report(mission, mission.spec.objective, model_text, provider)
        lease = self.leases.acquire(f"report:{mission.mission_id}", "vertex", mission.trace_id)
        try:
            if not mission.pending_approval_id:
                raise PermissionError("mission_report_write_missing_human_approval")
            receipt = self.tools.invoke(mission.mission_id, "file_write_report", {"path": f"{mission.mission_id}/mission-report.md", "content": report}, mission.trace_id, approval_id=mission.pending_approval_id, actor_id="runtime", task_id=mission.mission_id, idempotency_key=f"{mission.mission_id}:report-write")
        finally:
            self.leases.release(lease.lease_id, "vertex", mission.trace_id)
        mission.result["report_path"] = receipt.result["path"]
        mission.result["receipt_evidence_id"] = receipt.receipt_evidence_id
        mission.rollback_point = receipt.invocation_id
        self._save_mission(mission)
        self.recovery.checkpoint(mission.mission_id, "report_written", mission.trace_id, data={"path": receipt.result["path"]})
        self._advance(mission, MissionState.VERIFICATION, "reviewer")
        return self._verify_stage(mission)

    def _verify_stage(self, mission: Mission) -> Mission:
        vkey = f"{mission.mission_id}:verification_evidence"
        verification = self._verify_report(mission)
        parent = [mission.result["receipt_evidence_id"]] if mission.result.get("receipt_evidence_id") else None
        existing = self._get_evidence_by_idempotency(vkey, mission.mission_id)
        if existing:
            try:
                stored_verification = json.loads(existing.get("content", ""))
            except (TypeError, ValueError) as exc:
                raise ValueError("verification_evidence_invalid") from exc
            if not isinstance(stored_verification, dict):
                raise ValueError("verification_evidence_invalid")
            stable_fields = {"exists", "bytes", "non_empty", "sha256"}
            if (
                any(
                    stored_verification.get(field) != verification.get(field)
                    for field in stable_fields
                )
                or existing.get("parent_evidence", []) != (parent or [])
            ):
                raise ValueError("verification_evidence_conflict")
            result = type(
                "Evidence", (), {"evidence_id": existing["evidence_id"]}
            )()
        else:
            result = self.evidence.add(mission.mission_id, "verification_report", "VerificationReport", json.dumps(verification, ensure_ascii=False, indent=2), mission.trace_id, actor="reviewer", source="filesystem", verification_status="verified", parent_evidence=parent, idempotency_key=vkey)
        mission.result["verification_evidence_id"] = result.evidence_id
        self._save_mission(mission)
        self._advance(mission, MissionState.EVIDENCE, "reviewer")
        return self._commit_evidence_stage(mission)

    def _commit_evidence_stage(self, mission: Mission) -> Mission:
        ekey = f"{mission.mission_id}:execution_result_evidence"
        summary = json.dumps({"report_path": mission.result.get("report_path", "")}, ensure_ascii=False)
        re = self.evidence.add(mission.mission_id, "execution_result", "Execution result", summary, mission.trace_id, actor="reviewer", source="runtime", verification_status="verified", idempotency_key=ekey)
        mission.result["result_evidence_id"] = re.evidence_id
        self.recovery.checkpoint(mission.mission_id, "evidence_collected", mission.trace_id, data={"evidence_id": re.evidence_id})
        self._save_mission(mission)
        self._advance(mission, MissionState.MEMORY_PATCH, "archivist")
        return self._update_memory_stage(mission)

    def _update_memory_stage(self, mission: Mission) -> Mission:
        mkey = f"{mission.mission_id}:memory_patch"
        re_id = mission.result.get("result_evidence_id")
        if not re_id:
            for e in self.evidence.list(mission.mission_id):
                if e.get("kind") == "execution_result":
                    re_id = e.get("evidence_id")
                    break
        mem = self.memory.patch(mission.mission_id, "mission.completed_report", "A bounded local report was generated and verified.", mission.trace_id, re_id or "", idempotency_key=mkey)
        mission.result["memory_patch_id"] = mem.memory_id
        self._save_mission(mission)
        self._advance(mission, MissionState.EVALUATION, "kairos")
        return self._evaluate_stage(mission)

    def _evaluate_stage(self, mission: Mission) -> Mission:
        ek = f"{mission.mission_id}:evaluation"
        md = mission.result.get(f"{mission.mission_id}:model_tokens", {})
        it = int(md.get("input_tokens", 0)) if isinstance(md, dict) else 0
        ot = int(md.get("output_tokens", 0)) if isinstance(md, dict) else 0
        ev = self.evaluator.evaluate(mission, len(self.evidence.list(mission.mission_id)), len(self.tools.list_invocations(mission.mission_id)), it, ot, idempotency_key=ek)
        mission.result["evaluation_id"] = ev.evaluation_id
        mission.result["evaluation_passed"] = ev.passed
        self._save_mission(mission)
        self.recovery.checkpoint(mission.mission_id, "evaluation_completed", mission.trace_id, data={"passed": ev.passed})
        if self._completion_gate(mission, ev):
            self._advance(mission, MissionState.COMPLETED, "kairos")
        else:
            self._advance(mission, MissionState.BLOCKED, "kairos")
        self.scheduler.release(mission.assignments)
        return mission

    def _completion_gate(self, mission: Mission, evaluation) -> bool:
        if not mission.contract or mission.contract.status != "approved":
            return False
        if not evaluation.passed:
            return False
        if self.evidence.verify_all(mission.mission_id)["invalid"]:
            return False
        approvals = self.approvals.list(mission.mission_id)
        if mission.spec.risk_level.value in {"R2", "R3", "R4"} and not any(item.get("status") in {"approved", "consumed"} for item in approvals):
            return False
        return not any(item.get("state") == MissionState.BLOCKED.value for item in self.recovery.recover().missions if item.get("mission_id") == mission.mission_id)

    def _render_report(self, mission: Mission, task: str, model_text: str, provider: str) -> str:
        return f"# NEXARA PRIME Mission Report\n\n- Mission: `{mission.mission_id}`\n- Title: {mission.spec.title}\n- Risk: {mission.spec.risk_level.value}\n- Provider: {provider}\n\n## Compiled task\n\n{task}\n\n## Result\n\n{model_text}\n\n## Governance\n\nThis report was written only after human approval, under a Writer Lease, with an execution receipt and verification evidence.\n"

    def _verify_report(self, mission: Mission) -> dict:
        import hashlib
        path = Path(mission.result["report_path"])
        exists = path.exists()
        bytes_count = path.stat().st_size if exists else 0
        digest = hashlib.sha256(path.read_bytes()).hexdigest() if exists else None
        return {"exists": exists, "bytes": bytes_count, "non_empty": bytes_count > 0, "sha256": digest, "verified_at": now_iso()}

    def _find_evidence_by_idempotency(self, key: str, mission_id: str) -> Any:
        """Find existing evidence by idempotency_key using public EvidenceStore.list API.
        Returns an EvidenceArtifact (or any object with .evidence_id attribute)."""
        for e in self.evidence.list(mission_id):
            if e.get("idempotency_key") == key:
                # list() returns dicts with internal fields (envelope_sha256 etc.)
                # — reconstruct a minimal EvidenceArtifact with just evidence_id
                return type('Evidence', (), {'evidence_id': e['evidence_id']})()
        raise KeyError(f"evidence_not_found_by_idempotency_key:{key}")

    def _get_evidence_by_idempotency(
        self, key: str, mission_id: str
    ) -> dict[str, Any] | None:
        """Return an integrity-checked evidence projection for one replay key."""
        for evidence in self.evidence.list(mission_id):
            if evidence.get("idempotency_key") == key:
                return evidence
        return None

    def pause(self, mission_id: str) -> Mission:
        mission = self._load_mission(mission_id)
        mission.paused = True
        self._save_mission(mission)
        self.events.publish("mission.paused", mission_id, "mission", "human", mission.trace_id, {}, idempotency_key=f"mission-paused:{mission_id}:{mission.updated_at}")
        return mission

    def resume(self, mission_id: str) -> Mission:
        """Unpause a paused mission. Does NOT reset mission state —
        run_mission() dispatches from persisted state."""
        mission = self._load_mission(mission_id)
        if mission.paused:
            mission.paused = False
            self._save_mission(mission)
            self.events.publish("mission.resumed", mission_id, "mission", "human", mission.trace_id, {}, idempotency_key=f"mission-resumed:{mission_id}:{mission.updated_at}")
        return mission

    def inspect_mission(self, mission_id: str) -> dict[str, Any]:
        """Single authoritative runtime truth snapshot. Includes SDK compatibility
        fields (state, spec, title, objective, created_at) so API/CLI/UI don't
        patch separately. Merges provider_unavailable from runtime init + mission recovery."""
        mission = self._load_mission(mission_id)
        evidence_list = self.evidence.list(mission_id)
        # Approval status from ApprovalEngine records
        approval_status = "not_required"
        if mission.pending_approval_id:
            approval_status = "pending"
            try:
                approvals = self.approvals.list(mission_id)
                for a in approvals:
                    if a.get("approval_id") == mission.pending_approval_id:
                        approval_status = a.get("status", "pending")
                        break
            except Exception as exc:
                approval_status = "integrity_error"
                self.audit.record("approval.integrity_failure", actor_id="inspect_mission", actor_type="system", mission_id=mission_id, action="inspect_mission", decision="integrity_error", risk_level=mission.spec.risk_level.value if mission.spec.risk_level else "R0", trace_id=mission.trace_id, metadata={"error": str(exc)[:500]})
        # Provider unavailability: merge runtime init flag + mission recovery flag
        runtime_unavailable = getattr(self, '_provider_unavailable', False)
        mission_recovery = mission.result.get("recovery", {}) if isinstance(mission.result, dict) else {}
        mission_unavailable = mission_recovery.get("provider_unavailable", False)
        provider_unavailable = runtime_unavailable or mission_unavailable
        # A report receipt must bind to this mission's file_write_report tool;
        # an unrelated code execution receipt cannot satisfy completion truth.
        tool_by_id = {
            item.get("invocation_id"): item
            for item in self.tools.list_invocations(mission_id)
        }
        expected_receipt_id = mission.result.get("receipt_evidence_id")
        receipt_present = any(
            evidence.get("kind") == "execution_receipt"
            and (
                not expected_receipt_id
                or evidence.get("evidence_id") == expected_receipt_id
            )
            and tool_by_id.get(evidence.get("tool_invocation_id"), {}).get(
                "tool_name"
            )
            == "file_write_report"
            for evidence in evidence_list
        )
        return {
            "mission_id": mission.mission_id,
            "state": mission.state, "current_state": mission.state,
            "risk_level": mission.spec.risk_level.value if mission.spec.risk_level else "R0",
            "spec": mission.spec.model_dump(mode="json"),
            "title": mission.spec.title, "objective": mission.spec.objective,
            "created_at": mission.created_at, "started_at": mission.created_at,
            "updated_at": mission.updated_at,
            "provider": self.models.provider.name if hasattr(self.models, 'provider') else "mock",
            "provider_unavailable": provider_unavailable,
            "approval_status": approval_status, "pending_action": mission.pending_approval_id or None,
            "evidence_count": len(evidence_list),
            "latest_evidence": evidence_list[-1] if evidence_list else None,
            "receipt_status": "present" if receipt_present else "missing",
            "memory_patch_status": "patched" if mission.result.get("memory_patch_id") else "not_patched",
            "evaluation_status": "passed" if mission.result.get("evaluation_passed") else ("failed" if "evaluation_id" in (mission.result or {}) else "not_evaluated"),
            "retry_count": mission.result.get("retry_count", 0) if isinstance(mission.result, dict) else 0,
            "recovery_pointer": mission.rollback_point,
            "terminal_reason": mission.result.get("error") if mission.state in {"Failed", "Blocked"} else None,
            "paused": mission.paused, "safe_mode": mission.safe_mode, "trace_id": mission.trace_id,
        }

    def takeover(self, mission_id: str) -> Mission:
        mission = self._load_mission(mission_id)
        self.events.publish("mission.takeover", mission_id, "mission", "human", mission.trace_id, {"previous_owner": "runtime"})
        mission.result["owner"] = "human"
        self._save_mission(mission)
        return mission

    def rollback(self, mission_id: str) -> Mission:
        mission = self._load_mission(mission_id)
        if mission.state == MissionState.ROLLED_BACK.value:
            return mission
        previous_state = mission.state
        self._advance(mission, MissionState.ROLLED_BACK, "human")
        mission.result["rollback_at"] = now_iso()
        self._save_mission(mission)
        self.evidence.add(mission_id, "rollback_point", "RollbackPoint", json.dumps({"previous_state": previous_state, "checkpoint": mission.rollback_point}), mission.trace_id, actor="human", source="governance", verification_status="verified")
        return mission

    def safe_mode(self, mission_id: str, enabled: bool = True) -> Mission:
        mission = self._load_mission(mission_id)
        mission.safe_mode = enabled
        self._save_mission(mission)
        self.events.publish("governance.safe_mode.changed", mission_id, "mission", "human", mission.trace_id, {"enabled": enabled})
        return mission

    def recover(self):
        return self.recovery.recover()

    def overview(self) -> dict:
        _ensure_adapters(self)
        adapter_status = {
            "browser": _browser_adapter is not None,
            "computer_use": _computer_use_adapter is not None,
            "git": _git_adapter is not None,
            "messenger": _message_adapter is not None,
            "deployment": _deployment_adapter is not None,
            "rag_pipeline": _rag_pipeline is not None,
            "memory_layer_manager": _memory_layer_manager is not None,
            "repair_loop": _repair_loop is not None,
            "program_loop": _program_loop is not None,
        }
        return {"system": {"name": "NEXARA PRIME", "mode": self.models.provider.name, "healthy": True, "human_control": True, "mock_default": self.settings.mock_model, "adapters": adapter_status}, "missions": self.list_missions()[-20:], "approvals": self.approvals.list()[-20:], "evidence": self.evidence.list()[-20:], "tools": self.tools.list_invocations()[-20:], "capabilities": self.capabilities.list(), "recovery": self.recover().__dict__}

    def health(self) -> dict:
        return {"status": "ok", "provider": self.models.provider.name, "db_path": str(self.settings.db_path), "event_count": len(self.store.list_events()), "recovery": self.recover().__dict__}

    # ── Adaptive Runtime Methods ──

    def _get_adaptive(self) -> AdaptiveOrchestrator | None:
        """Lazy-build the adaptive orchestrator."""
        _ensure_adaptive_imports()
        if None in (_adaptive_triage, _adaptive_scheduler_v2, _adaptive_capabilities_v2, _adaptive_router, _adaptive_budgets, _adaptive_escalation, _adaptive_tokens_v2):
            return None
        return AdaptiveOrchestrator(
            triage_engine=_adaptive_triage,
            scheduler=_adaptive_scheduler_v2,
            capability_registry=_adaptive_capabilities_v2,
            model_router=_adaptive_router,
            budget_manager=_adaptive_budgets,
            escalation_engine=_adaptive_escalation,
            token_compiler=_adaptive_tokens_v2,
            store=self.store,
            events=self.events,
            evidence=self.evidence,
            audit=self.audit,
            approvals=self.approvals,
            tools=self.tools,
            state_machine=self.state_machine,
            recovery=self.recovery,
        )

    def adaptive_status(self) -> dict:
        """Return live adaptive runtime status."""
        orch = self._get_adaptive()
        missions_raw = self.list_missions()
        profiles = []
        for m in missions_raw[-10:]:
            mission_id = m.get("mission_id", "")
            try:
                mission = self._load_mission(mission_id)
            except KeyError:
                continue
            profile = AdaptiveMissionProfile(
                mission_id=mission_id,
                adaptive_mode=mission.adaptive_mode or "UNKNOWN",
                active_agents=[a.persona.value for a in (mission.assignments or [])],
                selected_provider="deepseek" if mission.routing_decisions else "UNKNOWN",
                selected_model=(mission.routing_decisions[-1].get("selected_model", "UNKNOWN") if mission.routing_decisions else "UNKNOWN"),
                token_budget=int((mission.resource_budget or {}).get("token_budget", 0)),
                token_used=int((mission.budget_usage or {}).get("tokens_used", 0)),
                cost_estimate=float((mission.resource_budget or {}).get("cost_budget", 0)),
                tool_calls=int((mission.budget_usage or {}).get("tool_calls_used", 0)),
                retries=int((mission.budget_usage or {}).get("retries_used", 0)),
                approval_state=mission.state or "UNKNOWN",
                evidence_count=len(self.evidence.list(mission_id)),
                escalation_count=len(mission.escalation_history),
            )
            profiles.append(profile.model_dump(mode="json"))
        return {"adaptive_runtime": "active" if orch else "degraded", "missions": profiles}

    def adaptive_explain(self, mission_id: str) -> dict:
        """Explain adaptive decisions for a mission."""
        orch = self._get_adaptive()
        if not orch:
            return {"error": "adaptive_runtime_not_available", "mission_id": mission_id}
        try:
            mission = self._load_mission(mission_id)
            return orch.explain_mission(mission)
        except KeyError:
            return {"error": "mission_not_found", "mission_id": mission_id}

    def adaptive_budget(self, mission_id: str) -> dict:
        """Get budget status for a mission."""
        try:
            mission = self._load_mission(mission_id)
            budget = mission.resource_budget or {}
            usage = mission.budget_usage or {}
            return {
                "mission_id": mission_id,
                "budget": budget,
                "usage": usage,
                "within_budget": not usage.get("stopped", False),
                "degraded": usage.get("degraded", False),
            }
        except KeyError:
            return {"error": "mission_not_found", "mission_id": mission_id}

    def adaptive_agents(self, mission_id: str) -> dict:
        """Get agent assignments for a mission."""
        try:
            mission = self._load_mission(mission_id)
            return {
                "mission_id": mission_id,
                "adaptive_mode": mission.adaptive_mode or "UNKNOWN",
                "active_agents": [a.model_dump(mode="json") if hasattr(a, 'model_dump') else a for a in (mission.assignments or [])],
                "agent_lifecycle": mission.agent_lifecycle,
                "scheduling_plan": mission.scheduling_plan,
            }
        except KeyError:
            return {"error": "mission_not_found", "mission_id": mission_id}

    def adaptive_route(self, mission_id: str) -> dict:
        """Get routing decisions for a mission."""
        try:
            mission = self._load_mission(mission_id)
            return {
                "mission_id": mission_id,
                "routing_decisions": mission.routing_decisions,
                "current": mission.routing_decisions[-1] if mission.routing_decisions else None,
            }
        except KeyError:
            return {"error": "mission_not_found", "mission_id": mission_id}

    def adaptive_triage(self, mission_id: str) -> dict:
        """Run triage on an existing mission."""
        orch = self._get_adaptive()
        if not orch:
            return {"error": "adaptive_runtime_not_available"}
        try:
            mission = self._load_mission(mission_id)
            result = orch.triage_mission(mission)
            self._save_mission(mission)
            return result.model_dump(mode="json")
        except KeyError:
            return {"error": "mission_not_found", "mission_id": mission_id}
