from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
from datetime import datetime, timezone
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
from .independent_review import IndependentReview
from .memory import MemoryKernel
from .mission_compiler import MissionCompiler
from .model_gateway import LocalModelProvider, ModelGateway, MockProvider, OpenAICompatibleProvider, ProviderUnavailable, UnavailableProvider, redact_secrets
from .conversations import ConversationStore
from .conversation_intent import IntentDecision, RuntimeIntentClassifier
from .models import (
    Mission, MissionState, RiskLevel, AdaptiveMissionProfile,
    now_iso, new_id,
)
from .recovery import DurableRecovery
from .real_context import ContextCollectionError, RealRepositoryContext, RepositoryContext
from .scheduler import AdaptiveScheduler
from .security_audit import SecurityAuditLedger
from .state_machine import MissionStateMachine
from .token_compiler import TokenCompiler
from .tools import ToolRuntime
from .telemetry import TelemetryService
from .brain.kernel import ChiefBrainKernel
from .mission_triage import MissionTriageEngine
from .orchestration import RuntimeOrchestrator
from .adaptive_scheduler import AdaptiveMultiAgentScheduler

# ── Runtime Closure v1: Governed Adapters ──
_ADAPTERS_INITIALIZED = False
_browser_adapter = None
_computer_use_adapter = None
_git_adapter = None
_message_adapter = None
_deployment_adapter = None
_rag_pipeline = None
_memory_layer_manager = None
_cbk = None
_repair_loop = None
_program_loop = None
_adapters_lock = threading.Lock()

def _ensure_adapters(runtime):
    global _ADAPTERS_INITIALIZED, _browser_adapter, _computer_use_adapter
    global _git_adapter, _message_adapter, _deployment_adapter
    global _rag_pipeline, _memory_layer_manager, _cbk, _repair_loop, _program_loop
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
            global _cbk
            _cbk = ChiefBrainKernel(
                triage=MissionTriageEngine(),
                compiler=runtime.compiler,
                contracts=runtime.contracts,
                state_machine=runtime.state_machine,
                orchestrator=RuntimeOrchestrator(runtime.store, runtime.events, runtime.evidence),
                scheduler=AdaptiveMultiAgentScheduler(),
                policy=runtime.policy,
                approvals=runtime.approvals,
                memory_layer_manager=_memory_layer_manager,
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
# Shared CircuitBreaker — single authority for ModelGateway + ModelRouter
_shared_breaker = None

def _ensure_adaptive_imports():
    global _ADAPTIVE_IMPORTS_DONE, _adaptive_triage, _adaptive_scheduler_v2
    global _adaptive_capabilities_v2, _adaptive_router, _adaptive_budgets
    global _adaptive_escalation, _adaptive_tokens_v2, _shared_breaker
    if _ADAPTIVE_IMPORTS_DONE:
        return
    try:
        from .model_router import CircuitBreaker
        _shared_breaker = CircuitBreaker()
    except ImportError:
        pass
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
        _adaptive_router = ModelRouter(breaker=_shared_breaker)
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
        self._started_at = datetime.now(timezone.utc)
        self._last_success_at: str = ""
        self._last_failure_at: str = ""
        self.store = SQLiteStore(self.settings.db_path)
        self.events = EventBus(self.store)
        self.audit = SecurityAuditLedger(self.store)
        self.evidence = EvidenceStore(self.store, self.events)
        self.memory = MemoryKernel(self.store, self.events, self.evidence)
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
        self.repository_context = RealRepositoryContext()
        self.telemetry = TelemetryService(self.events)
        self.telemetry.start()
        self.conversations = ConversationStore(self.store, self.events, self.audit)
        self._mission_threads: dict[str, threading.Thread] = {}
        self._mission_threads_lock = threading.RLock()
        # Opt-in only: main's crash-recovery semantics assume the caller owns
        # resumption. Enabling auto-resume is a conversation-product choice.
        if os.getenv("NEXARA_RESUME_BACKGROUND_MISSIONS", "false").lower() in {"1", "true", "yes", "on"}:
            self._resume_background_missions()

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

    @property
    def cbk(self):
        """ChiefBrainKernel — sole Mission Admission Boundary. Lazy-initialized."""
        _ensure_adapters(self)
        return _cbk

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
        elif provider_name == "deepseek":
            api_key = self._resolve_api_key("deepseek_api_key", "DEEPSEEK_API_KEY")
            if not api_key:
                self._provider_unavailable = True
                return ModelGateway(UnavailableProvider())
            provider = OpenAICompatibleProvider(
                os.getenv("NEXARA_MODEL_ENDPOINT", "https://api.deepseek.com/v1"),
                model=os.getenv("NEXARA_MODEL_NAME", "deepseek-chat"),
                api_key=api_key,
                provider_name="deepseek",
                max_output_tokens=int(os.getenv("NEXARA_MAX_OUTPUT_TOKENS", "4096")),
                timeout_seconds=float(os.getenv("NEXARA_MODEL_TIMEOUT", "120")),
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
        return ModelGateway(
            provider,
            fallback=None,
            max_attempts=int(os.getenv("NEXARA_PROVIDER_MAX_ATTEMPTS", "2")),
            retry_delay_seconds=float(os.getenv("NEXARA_PROVIDER_RETRY_DELAY_SECONDS", "0.25")),
            breaker=_shared_breaker,
        )

    @staticmethod
    def _resolve_api_key(secret_name: str, env_var: str) -> str | None:
        """Resolve Keychain first, with an explicit environment fallback."""
        require_keychain = os.getenv("NEXARA_REQUIRE_KEYCHAIN_CREDENTIAL", "").lower() in {"1", "true", "yes"}
        try:
            from .secrets.keychain import MacOSKeychainSecretStore
            store = MacOSKeychainSecretStore()
            if store.exists(secret_name):
                return store.get(secret_name)
        except (ImportError, RuntimeError, OSError):
            pass
        if require_keychain:
            raise RuntimeError(f"keychain_credential_required:{secret_name}")
        return os.getenv(env_var)

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

    @staticmethod
    def _normalize_objective(value: str) -> str:
        return " ".join(value.strip().lower().split())

    def _find_resumable_mission(self, objective: str) -> Mission | None:
        normalized = self._normalize_objective(objective)
        terminal = {
            MissionState.COMPLETED.value,
            MissionState.FAILED.value,
            MissionState.BLOCKED.value,
            MissionState.ROLLED_BACK.value,
        }
        for raw in reversed(self.list_missions()):
            if self._normalize_objective(raw.get("spec", {}).get("objective", "")) != normalized:
                continue
            if raw.get("state") in terminal:
                continue
            return self._load_mission(raw["mission_id"])
        return None

    def _start_background_execution(self, mission_id: str) -> None:
        """Run an approved local Mission independently of the UI process."""
        with self._mission_threads_lock:
            current = self._mission_threads.get(mission_id)
            if current and current.is_alive():
                return
            worker = threading.Thread(
                target=self._background_execute,
                args=(mission_id,),
                name=f"nexara-mission-{mission_id}",
                daemon=True,
            )
            self._mission_threads[mission_id] = worker
            worker.start()

    def _resume_background_missions(self) -> None:
        resumable = {
            MissionState.EXECUTION.value,
            MissionState.VERIFICATION.value,
            MissionState.EVIDENCE.value,
            MissionState.MEMORY_PATCH.value,
            MissionState.EVALUATION.value,
        }
        for raw in self.list_missions():
            if raw.get("state") in resumable and not raw.get("paused", False):
                self._start_background_execution(raw["mission_id"])

    def _background_execute(self, mission_id: str) -> None:
        self.telemetry.record_health("mission", "background_execution_started", f"mission_id={mission_id}")
        try:
            mission = self.run_mission(mission_id)
            if mission.state == MissionState.COMPLETED.value:
                self._notify_mission_completed(mission)
                self.telemetry.record_health("mission", "background_execution_completed", f"mission_id={mission_id}")
            else:
                self.telemetry.record_health("mission", "background_execution_stopped", f"mission_id={mission_id};state={mission.state}")
        except Exception as exc:
            self.telemetry.record_health("mission", "background_execution_failed", f"mission_id={mission_id};error={redact_secrets(str(exc))[:160]}")
        finally:
            with self._mission_threads_lock:
                self._mission_threads.pop(mission_id, None)

    def _notify_mission_completed(self, mission: Mission) -> None:
        notification_id = f"notification_{mission.mission_id}_completed"
        timestamp = now_iso()
        payload = {
            "notification_id": notification_id,
            "mission_id": mission.mission_id,
            "kind": "mission_completed",
            "title": "NEXARA Canary",
            "body": "Mission 已完成，Evidence 与 Memory 已保存。",
            "created_at": timestamp,
        }
        if self.store.save_record_if_absent(notification_id, "notification", payload, timestamp, mission.mission_id):
            self.events.publish(
                "notification.mission_completed",
                mission.mission_id,
                "notification",
                "nexara.runtime",
                mission.trace_id,
                {"notification_id": notification_id},
                idempotency_key=notification_id,
            )
            if shutil.which("osascript"):
                try:
                    subprocess.run(
                        ["osascript", "-e", 'display notification "Mission 已完成，Evidence 与 Memory 已保存。" with title "NEXARA Canary"'],
                        check=False,
                        capture_output=True,
                        text=True,
                        timeout=3,
                    )
                except (OSError, subprocess.SubprocessError):
                    self.telemetry.record_health("notification", "local_notification_failed", "osascript_failed")

    def _resolve_execution_mode(self, content: str, execution_mode: str) -> tuple[str, IntentDecision]:
        if execution_mode not in {"chat", "auto", "mission"}:
            raise ValueError("execution_mode_invalid")
        if execution_mode == "auto":
            decision = RuntimeIntentClassifier.classify(content)
            return decision.intent, decision
        if execution_mode == "mission":
            return "mission", IntentDecision("mission", 1.0, ("explicit_mission_mode",))
        return "chat", IntentDecision("chat", 1.0, ("explicit_chat_mode",))

    def answer_conversation(
        self,
        conversation_id: str,
        content: str,
        *,
        execution_mode: str = "chat",
        execute_mission: bool | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Persist one user turn, route it through the configured provider, and persist the reply."""
        self.conversations.get(conversation_id)
        if execute_mission is True:
            execution_mode = "mission"
        intent, intent_decision = self._resolve_execution_mode(content, execution_mode)
        existing_user = None
        if idempotency_key:
            existing = self.conversations.find_message_by_idempotency(
                conversation_id, idempotency_key
            )
            if existing is not None:
                if existing.get("content") != content.strip() or existing.get("role") != "user":
                    raise ValueError("conversation_idempotency_conflict")
                assistant = self.conversations.find_assistant_response(
                    conversation_id, existing["message_id"]
                )
                if assistant is not None:
                    return {
                        "conversation": self.conversations.get(conversation_id),
                        "user_message": existing,
                        "assistant_message": assistant,
                        "mission_id": assistant.get("metadata", {}).get("mission_id"),
                        "approval_required": bool(
                            assistant.get("metadata", {}).get("approval_required", False)
                        ),
                        "provider": assistant.get("metadata", {}).get("provider"),
                        "execution_mode": assistant.get("metadata", {}).get("execution_mode", execution_mode),
                        "intent": assistant.get("metadata", {}).get("intent", intent),
                        "idempotent_replay": True,
                    }
                existing_user = existing

        if existing_user is not None:
            user_message = existing_user
            trace_id = str(existing_user.get("trace_id") or new_id("trace"))
            existing_mode = (existing_user.get("metadata") or {}).get("execution_mode")
            if existing_mode in {"chat", "auto", "mission"}:
                execution_mode = existing_mode
                intent, intent_decision = self._resolve_execution_mode(content, execution_mode)
        else:
            trace_id = new_id("trace")
            user_message = self.conversations.append_message(
                conversation_id,
                "user",
                content,
                trace_id=trace_id,
                idempotency_key=idempotency_key,
                metadata={
                    "execution_mode": execution_mode,
                    "intent": intent,
                    "intent_confidence": intent_decision.confidence,
                    "intent_reasons": list(intent_decision.reasons),
                },
            )
        mission_id: str | None = None
        approval_required = False
        if intent == "mission":
            previous_attempts = self.conversations.provider_attempts(conversation_id, user_message["message_id"])
            mission_id = next((item.get("mission_id") for item in reversed(previous_attempts) if item.get("mission_id")), None)
            if mission_id is None:
                mission = self._find_resumable_mission(content) or self.create_mission(content)
                if mission.state == MissionState.INTENT.value:
                    self.plan_mission(mission.mission_id)
                mission_id = mission.mission_id
            current_mission = self._load_mission(mission_id)
            approval_required = bool(current_mission.pending_approval_id)
            current_mission.result["execution_mode"] = execution_mode
            current_mission.result["background_execution"] = True
            self._save_mission(current_mission)
            if current_mission.state == MissionState.EXECUTION.value and not approval_required:
                self._start_background_execution(mission_id)

        transcript = self.conversations.messages(conversation_id)[-12:]
        transcript_text = "\n".join(
            f"{item['role']}: {item['content']}" for item in transcript
        )
        system = (
            "You are NEXARA PRIME, the user's first-party governed runtime. "
            "Answer directly and honestly. Never claim an action completed "
            "unless the runtime has evidence for it."
        )
        task = (
            "Respond to the latest user message in this durable conversation.\n"
            f"Conversation transcript:\n{transcript_text}\n"
            f"Execution mode: {execution_mode}\n"
            f"Runtime intent: {intent}\n"
            f"Intent confidence: {intent_decision.confidence:.2f}\n"
            f"Mission admitted: {mission_id or 'no'}\n"
            f"Approval required: {'yes' if approval_required else 'no'}"
        )
        attempt_number = len(self.conversations.provider_attempts(conversation_id, user_message["message_id"])) + 1
        attempt = {
            "attempt_id": f"provider_attempt_{user_message['message_id']}_{attempt_number}",
            "conversation_id": conversation_id,
            "message_id": user_message["message_id"],
            "mission_id": mission_id,
            "provider": self.models.provider.name,
            "model": getattr(self.models.provider, "model", ""),
            "status": "started",
            "attempt_number": attempt_number,
            "created_at": now_iso(),
            "request_id": "",
            "latency_ms": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "finish_reason": "",
            "retry_count": 0,
            "error_code": None,
            "reasoning_tokens": None,
            "cost_usd": None,
        }
        self.conversations.save_provider_attempt(attempt)
        self.telemetry.record_health("provider", "starting", f"provider={self.models.provider.name}")
        try:
            response = self.models.complete(
                system,
                task,
                {"conversation_id": conversation_id, "trace_id": trace_id},
                trace_id=trace_id,
            )
        except Exception as exc:
            attempt.update({"status": "failed", "error_code": getattr(exc, "code", "provider_failed"), "error": redact_secrets(str(exc))})
            self.conversations.save_provider_attempt(attempt)
            self.telemetry.record_health("provider", "degraded", str(attempt["error_code"]))
            raise
        attempt.update({
            "status": "succeeded",
            "provider": response.provider,
            "model": response.model,
            "request_id": response.request_id,
            "latency_ms": response.latency_ms,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "total_tokens": response.total_tokens,
            "finish_reason": response.finish_reason,
            "retry_count": response.retry_count,
            "reasoning_tokens": response.reasoning_tokens,
            "cost_usd": response.cost_usd,
        })
        self.conversations.save_provider_attempt(attempt)
        self.telemetry.record_health("provider", "healthy", f"provider={response.provider}")
        assistant_message = self.conversations.append_message(
            conversation_id,
            "assistant",
            response.text,
            trace_id=trace_id,
            metadata={
                "provider": response.provider,
                "model": response.model,
                "mission_id": mission_id,
                "execution_mode": execution_mode,
                "intent": intent,
                "intent_confidence": intent_decision.confidence,
                "approval_required": approval_required,
                "response_to": user_message["message_id"],
                "request_id": response.request_id,
                "latency_ms": response.latency_ms,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "total_tokens": response.total_tokens,
                "finish_reason": response.finish_reason,
                "retry_count": response.retry_count,
                "provider_attempt_id": attempt["attempt_id"],
            },
        )
        return {
            "conversation": self.conversations.get(conversation_id),
            "user_message": user_message,
            "assistant_message": assistant_message,
            "mission_id": mission_id,
            "approval_required": approval_required,
            "provider": response.provider,
            "execution_mode": execution_mode,
            "intent": intent,
            "intent_confidence": intent_decision.confidence,
            "idempotent_replay": False,
        }

    def _advance(self, mission: Mission, target: MissionState, actor: str) -> None:
        previous = mission.state
        self.state_machine.transition(mission, target, actor)
        self._save_mission(mission)
        self.audit.record(
            "mission.state_changed", actor_id=actor, actor_type="system", mission_id=mission.mission_id,
            action=f"{previous}->{target.value}", decision="allowed", risk_level=mission.spec.risk_level.value,
            trace_id=mission.trace_id, metadata={"from_state": previous, "to_state": target.value},
        )

    def _collect_repository_context(self, mission: Mission) -> RepositoryContext | None:
        if not mission.spec.source_dir:
            return None
        try:
            source_root = Path(mission.spec.source_dir).resolve()
            source_root.relative_to(self.settings.workspace_root.resolve())
        except ValueError:
            return None
        try:
            return self.repository_context.collect(mission.spec.source_dir)
        except (ContextCollectionError, RuntimeError):
            return None

    def _execution_context(self, mission: Mission) -> RepositoryContext | None:
        context = self._collect_repository_context(mission)
        expected = mission.result.get("context_hash")
        if expected and (context is None or context.context_hash != expected):
            raise ValueError("context_hash_mismatch")
        return context

    def _assignment_lifecycle(self, mission: Mission, assignment, status: str, actor: str, step_id: str | None = None) -> None:
        assignment.status = status
        assignment.current_step_id = step_id
        item = {
            "assignment_id": assignment.assignment_id,
            "mission_id": mission.mission_id,
            "role": assignment.runtime_role.value,
            "persona": assignment.persona.value,
            "step_id": step_id,
            "status": status,
            "actor": actor,
            "timestamp": now_iso(),
        }
        mission.agent_lifecycle.append(item)
        self.events.publish("assignment.lifecycle", mission.mission_id, "assignment", actor, mission.trace_id, item, idempotency_key=f"assignment:{assignment.assignment_id}:{status}:{step_id or ''}")

    def _assignment_for_role(self, mission: Mission, role: str):
        return next((a for a in mission.assignments if a.runtime_role.value == role), None)

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
        repository_context = self._collect_repository_context(mission)
        if repository_context:
            mission.result["context_hash"] = repository_context.context_hash
            mission.result["context_manifest"] = repository_context.manifest()
            context_summary = json.dumps(repository_context.manifest(), ensure_ascii=False, sort_keys=True)
            self.evidence.add(mission.mission_id, "repository_context", "Real Git and file context", context_summary, mission.trace_id, actor="nexara", source="real_repository_context", verification_status="verified", idempotency_key=f"{mission.mission_id}:repository-context")
        self.recovery.checkpoint(mission.mission_id, "context_assembled", mission.trace_id, data={"summary": context_summary})
        self._advance(mission, MissionState.CONTRACT, "nexara")
        mission.contract = self.contracts.create(mission.spec)
        self._save_mission(mission)
        self.recovery.checkpoint(mission.mission_id, "contract_created", mission.trace_id, data={"contract_id": mission.contract.contract_id})
        self._advance(mission, MissionState.PLAN, "nexara")
        mission.assignments = self.scheduler.schedule(mission.spec, self.models.provider.name)
        steps = [{"role": assignment.runtime_role.value, "persona": assignment.persona.value, "capabilities": assignment.loaded_capabilities} for assignment in mission.assignments]
        mission.plan = self._build_plan(mission, steps)
        for assignment, step in zip(mission.assignments, mission.plan.steps):
            step.status = "assigned"
            self._assignment_lifecycle(mission, assignment, "assigned", "scheduler", step.step_id)
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
            if mission.result.get("background_execution"):
                self._start_background_execution(mission.mission_id)
        elif decision_record.status.value == "paused":
            mission.paused = True
            self._save_mission(mission)
        elif decision_record.status.value == "changes_requested":
            mission.result["approval_feedback"] = note
            self._save_mission(mission)
        else:
            self._advance(mission, MissionState.BLOCKED, actor)
        return mission

    def _checkpointed_model(self, mission: Mission, compiled, context: dict) -> tuple[str, str, int, int, float | None]:
        tk = f"{mission.mission_id}:model_tokens"
        p = mission.result.get(tk)
        if p and isinstance(p, dict) and int(p.get("input_tokens", 0)) > 0:
            return mission.result.get("model_text", ""), p.get("provider", "unknown"), int(p["input_tokens"]), int(p["output_tokens"]), p.get("cost_usd")
        # Migrate the durable response written by the pre-convergence runtime.
        # This check must precede the provider call or a restart can duplicate
        # an already completed and billed model request.
        legacy_key = f"{mission.mission_id}:model-completion"
        legacy_raw = self.store.find_record(
            "model_response", "idempotency_key", legacy_key
        )
        legacy_envelope = self.store.find_record_envelope(
            "model_response", "idempotency_key", legacy_key
        )
        if legacy_raw and not legacy_envelope:
            raise ValueError("model_response_integrity_invalid")
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
        if context.get("context_hash") and model_response.provider != "mock":
            returned_hash = model_response.metadata.get("context_hash")
            if returned_hash != context["context_hash"]:
                raise ValueError("provider_context_hash_unbound")
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
        # ── Timeout check (Runtime Productization v1) ──
        if mission.state not in {MissionState.COMPLETED.value, MissionState.ROLLED_BACK.value, MissionState.FAILED.value}:
            max_seconds = self.settings.max_execution_seconds
            if max_seconds and max_seconds > 0:
                elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(mission.created_at)).total_seconds()
                if elapsed > max_seconds:
                    mission.result["timeout"] = {"elapsed_seconds": elapsed, "max_seconds": max_seconds}
                    self._advance(mission, MissionState.FAILED, "runtime")
                    self._save_mission(mission)
                    raise TimeoutError(f"mission_timeout: {elapsed:.0f}s > {max_seconds}s")
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
        context_object = self._execution_context(mission)
        context = context_object.to_provider_context(mission.mission_id) if context_object else {
            "source_dir": mission.spec.source_dir or "workspace",
            "roles": [a.persona.value for a in mission.assignments],
        }
        if context_object:
            mission.result["provider_context_hash"] = context_object.context_hash
            self._assignment_lifecycle(
                mission,
                self._assignment_for_role(mission, "Executor"),
                "running",
                "executor",
                next((s.step_id for s in (mission.plan.steps if mission.plan else []) if s.role.value == "Executor"), None),
            ) if self._assignment_for_role(mission, "Executor") else None
        model_key = f"{mission.mission_id}:model_tokens"
        persisted = mission.result.get(model_key)
        if persisted and isinstance(persisted, dict):
            mt = int(persisted.get("input_tokens", 0))
            ot = int(persisted.get("output_tokens", 0))
            c = persisted.get("cost_usd")
            model_text = mission.result.get("model_text", "")
            provider = persisted.get("provider", "unknown")
        else:
            compiled = self.tokens.compile(mission.spec, [cap for a in mission.assignments for cap in a.loaded_capabilities], ["MissionSpec", "WorkContract", "MissionPlan"], [e["evidence_id"] for e in self.evidence.list(mission.mission_id)], json.dumps(context))
            model_text, provider, mt, ot, c = self._checkpointed_model(mission, compiled, context)
            mission.result[model_key] = {"input_tokens": mt, "output_tokens": ot, "cost_usd": c, "provider": provider}
            mission.result["model_text"] = model_text
        try:
            code = self.tools.invoke(mission.mission_id, "code_exec", {"code": "print('nexara-prime local execution check')"}, mission.trace_id, safe_mode=mission.safe_mode, actor_id="runtime", task_id=mission.mission_id, idempotency_key=f"{mission.mission_id}:code-check")
            self.recovery.checkpoint(mission.mission_id, "tools_checked", mission.trace_id, data={"invocation_id": code.invocation_id, "status": "completed"})
        except PermissionError as exc:
            # The local health mission can still produce a truthful report when
            # the optional code probe is unavailable. The failed tool Receipt is
            # already durable; preserve the limitation instead of fabricating a
            # successful probe or bypassing the sandbox.
            if not str(exc).startswith("os_sandbox_denied"):
                raise
            mission.result["environment_limitation"] = "code_exec_probe_unavailable: sandbox enforcement unavailable"
            self.recovery.checkpoint(mission.mission_id, "tools_checked", mission.trace_id, data={"status": "environment_limited", "reason": "sandbox_enforcement_unavailable"})
            self._save_mission(mission)
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
        executor = self._assignment_for_role(mission, "Executor")
        if executor:
            step_id = executor.current_step_id
            if mission.plan:
                for step in mission.plan.steps:
                    if step.step_id == step_id:
                        step.status = "completed"
            self._assignment_lifecycle(mission, executor, "completed", "executor", step_id)
        self._save_mission(mission)
        self.recovery.checkpoint(mission.mission_id, "report_written", mission.trace_id, data={"path": receipt.result["path"]})
        self._advance(mission, MissionState.VERIFICATION, "reviewer")
        return self._verify_stage(mission)

    def _verify_stage(self, mission: Mission) -> Mission:
        vkey = f"{mission.mission_id}:verification_evidence"
        verification = self._verify_report(mission)
        context_object = self._execution_context(mission)
        if context_object:
            verification["context_hash"] = context_object.context_hash
            reviewer_assignment = self._assignment_for_role(mission, "Reviewer")
            if reviewer_assignment:
                self._assignment_lifecycle(mission, reviewer_assignment, "running", "reviewer", reviewer_assignment.current_step_id)
            reviewer = IndependentReview.reviewer_verdict(mission.mission_id, mission.result["report_path"], context_object)
            if not reviewer["passed"]:
                raise ValueError("independent_reviewer_rejected")
            reviewer_evidence = self.evidence.add(mission.mission_id, "reviewer_verdict", "Independent reviewer verdict", IndependentReview.encode(reviewer), mission.trace_id, actor="reviewer", source="independent_reviewer", verification_status="verified", idempotency_key=f"{mission.mission_id}:reviewer-verdict")
            mission.result["reviewer_evidence_id"] = reviewer_evidence.evidence_id
            if reviewer_assignment:
                self._assignment_lifecycle(mission, reviewer_assignment, "completed", "reviewer", reviewer_assignment.current_step_id)
        parent = [mission.result["receipt_evidence_id"]] if mission.result.get("receipt_evidence_id") else None
        existing = self._get_evidence_by_idempotency(vkey, mission.mission_id)
        if existing:
            try:
                stored_verification = json.loads(existing.get("content", ""))
            except (TypeError, ValueError) as exc:
                raise ValueError("verification_evidence_invalid") from exc
            if not isinstance(stored_verification, dict):
                raise ValueError("verification_evidence_invalid")
            # Verify evidence integrity via evidence store before relying on stored content
            self.evidence.verify(existing["evidence_id"])
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
        context_object = self._execution_context(mission)
        if context_object:
            auditor_assignment = self._assignment_for_role(mission, "Auditor")
            if auditor_assignment:
                self._assignment_lifecycle(mission, auditor_assignment, "running", "auditor", auditor_assignment.current_step_id)
            auditor = IndependentReview.auditor_verdict(mission.mission_id, context_object, self.evidence, self.memory)
            if not auditor["passed"]:
                raise ValueError("independent_auditor_rejected")
            auditor_evidence = self.evidence.add(mission.mission_id, "auditor_verdict", "Independent auditor verdict", IndependentReview.encode(auditor), mission.trace_id, actor="auditor", source="independent_auditor", verification_status="verified", parent_evidence=[re.evidence_id], idempotency_key=f"{mission.mission_id}:auditor-verdict")
            mission.result["auditor_evidence_id"] = auditor_evidence.evidence_id
            if auditor_assignment:
                self._assignment_lifecycle(mission, auditor_assignment, "completed", "auditor", auditor_assignment.current_step_id)
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
        for assignment in mission.assignments:
            self._assignment_lifecycle(mission, assignment, "released", "scheduler", assignment.current_step_id)
        self._save_mission(mission)
        return mission

    def _completion_gate(self, mission: Mission, evaluation) -> bool:
        if not mission.contract or mission.contract.status != "approved":
            return False
        if not evaluation.passed:
            return False
        if self.evidence.verify_all(mission.mission_id)["invalid"]:
            return False
        mem_id = mission.result.get("memory_patch_id")
        if mem_id:
            mem_envelope = self.store.get_record_envelope(mem_id)
            if not mem_envelope:
                return False
            mkey = f"{mission.mission_id}:memory_patch"
            idem_envelope = self.store.find_record_envelope("memory_idempotency", "idempotency_key", mkey)
            if not idem_envelope or idem_envelope.get("mission_id") != mission.mission_id:
                return False
            mapping = idem_envelope["payload"]
            if mapping.get("memory_id") != mem_id:
                return False
        approvals = self.approvals.list(mission.mission_id)
        if mission.spec.risk_level.value in {"R2", "R3", "R4"} and not any(item.get("status") in {"approved", "consumed"} for item in approvals):
            return False
        return not any(item.get("state") == MissionState.BLOCKED.value for item in self.recovery.recover().missions if item.get("mission_id") == mission.mission_id)

    def _render_report(self, mission: Mission, task: str, model_text: str, provider: str) -> str:
        context_hash = mission.result.get("context_hash", "not_applicable")
        manifest = mission.result.get("context_manifest", {})
        facts = "\n".join([
            f"- Repository Branch: `{manifest.get('branch', 'not_applicable')}`",
            f"- Repository HEAD: `{manifest.get('head_sha', 'not_applicable')}`",
            f"- Repository Dirty: `{manifest.get('dirty', False)}`",
            f"- Repository Files: `{manifest.get('file_count', 0)}`",
            f"- Context Hash: `{context_hash}`",
            f"- Environment Limitation: `{mission.result.get('environment_limitation', 'none')}`",
        ])
        return f"# NEXARA PRIME Mission Report\n\n- Mission: `{mission.mission_id}`\n- Title: {mission.spec.title}\n- Risk: {mission.spec.risk_level.value}\n- Provider: {provider}\n\n## Verified repository facts\n\n{facts}\n\n## Compiled task\n\n{task}\n\n## Result\n\n{model_text}\n\n## Governance\n\nThis report was written only after human approval, under a Writer Lease, with an execution receipt and verification evidence.\n"

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
        """Return an integrity-checked evidence projection for one replay key.

        Phase 2: delegates to EvidenceStore.find_by_idempotency() — no raw store access.
        """
        result = self.evidence.find_by_idempotency(key)
        if result and result.get("mission_id") != mission_id:
            raise ValueError("evidence_mission_mismatch")
        return result

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
        # Receipt status: delegate to EvidenceStore.receipt_status() — single authority.
        # No independent receipt_present judgment (KMA_INVARIANT_10).
        # Bind to expected report-receipt tool types and verify mission ID match.
        receipt = self.evidence.receipt_status(
            mission_id,
            tool_names=["file_write_report", "write_workspace_file"],
        )
        # Honor EvidenceStore.receipt_status() as single authority (KMA_INVARIANT_10).
        # No independent judgment — the store's status is the canonical receipt_status.
        receipt_status_value = receipt.get("status", "missing")
        return {
            "mission_id": mission.mission_id,
            "state": mission.state, "current_state": mission.state,
            "risk_level": mission.spec.risk_level.value if mission.spec.risk_level else "R0",
            "spec": mission.spec.model_dump(mode="json"),
            "plan": mission.plan.model_dump(mode="json") if mission.plan else None,
            "title": mission.spec.title, "objective": mission.spec.objective,
            "created_at": mission.created_at, "started_at": mission.created_at,
            "updated_at": mission.updated_at,
            "provider": self.models.provider.name if hasattr(self.models, 'provider') else "mock",
            "provider_unavailable": provider_unavailable,
            "approval_status": approval_status, "pending_action": mission.pending_approval_id or None,
            "evidence_count": len(evidence_list),
            "latest_evidence": evidence_list[-1] if evidence_list else None,
            "receipt_status": receipt_status_value,
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
        from . import __version__
        now = datetime.now(timezone.utc)
        uptime = round((now - self._started_at).total_seconds(), 2)
        provider_available = self.models.provider.name != "UnavailableProvider"
        database_health = "ok"
        try:
            self.store.count("records")
        except Exception:
            database_health = "unavailable"
        last_success = ""
        last_failure = ""
        try:
            for a in self.store.list_records("provider_attempt"):
                ts = a.get("created_at", "")
                if a.get("status") == "succeeded":
                    last_success = ts
                elif a.get("status") == "failed":
                    last_failure = ts
        except Exception:
            pass
        return {
            "status": "ok",
            "version": __version__,
            "pid": os.getpid(),
            "port": self.settings.api_port,
            "provider": self.models.provider.name,
            "provider_health": "healthy" if provider_available else "unavailable",
            "runtime_state": "healthy",
            "database_health": database_health,
            "uptime_seconds": uptime,
            "last_success_at": last_success,
            "last_failure_at": last_failure,
            "db_path": str(self.settings.db_path),
            "event_count": len(self.store.list_events()),
            "recovery": self.recover().__dict__,
        }

    def stats(self) -> dict:
        """Aggregated runtime statistics — lightweight polling endpoint."""
        missions = self.list_missions()
        total = len(missions)
        active = sum(1 for m in missions if m.get("state") not in ("Completed", "Failed", "RolledBack"))
        completed = sum(1 for m in missions if m.get("state") == "Completed")
        failed = sum(1 for m in missions if m.get("state") == "Failed")
        blocked = sum(1 for m in missions if m.get("state") == "Blocked")
        pending_approvals = len([a for a in self.approvals.list() if a.get("status") == "pending"])
        total_evidence = len(self.evidence.list())
        provider_available = self.models.provider.name != "UnavailableProvider"
        last_event = ""
        events = self.store.list_events()
        if events:
            last_event = events[-1].get("timestamp", "")
        return {
            "total_missions": total,
            "active_missions": active,
            "completed_missions": completed,
            "failed_missions": failed,
            "blocked_missions": blocked,
            "pending_approvals": pending_approvals,
            "total_evidence": total_evidence,
            "provider": self.models.provider.name,
            "provider_available": provider_available,
            "mock_mode": self.settings.mock_model,
            "recovery_state": self.recover().__dict__.get("state", "healthy"),
            "last_event_at": last_event,
        }

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

    def _aggregate_provider_usage(self, mission_id: str) -> dict[str, Any]:
        """Aggregate real provider token/cost usage for a mission from provider_attempt records."""
        from .brain.reasoning_budget import COST_TABLE
        attempts = self.store.list_records("provider_attempt", mission_id)
        total_input = total_output = total_reasoning = total_tokens = 0
        cost_usd = 0.0
        retry_count = 0
        for a in attempts:
            if a.get("status") != "succeeded":
                continue
            it = int(a.get("input_tokens", 0))
            ot = int(a.get("output_tokens", 0))
            rt = int(a.get("reasoning_tokens") or 0)
            total_input += it
            total_output += ot
            total_reasoning += rt
            total_tokens += int(a.get("total_tokens", it + ot))
            retry_count += int(a.get("retry_count", 0))
            c = a.get("cost_usd")
            if c is not None:
                cost_usd += float(c)
            else:
                model = a.get("model", "mock")
                costs = COST_TABLE.get(model, COST_TABLE["mock"])
                cost_usd += (it / 1000) * costs["input"] + (ot / 1000) * costs["output"]
        return {
            "tokens_used": total_tokens,
            "input_tokens": total_input,
            "output_tokens": total_output,
            "reasoning_tokens": total_reasoning,
            "cost_used": round(cost_usd, 8),
            "retries": retry_count,
        }

    def adaptive_budget(self, mission_id: str) -> dict:
        """Get budget status for a mission, with real token/cost aggregation."""
        try:
            mission = self._load_mission(mission_id)
            budget = mission.resource_budget or {}
            usage = mission.budget_usage or {}
            real = self._aggregate_provider_usage(mission_id)
            if real:
                usage = {**usage, **real}
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
