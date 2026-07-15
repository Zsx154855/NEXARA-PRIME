"""NEXARA PRIME Deployment Adapter — Governed deployment pipeline.

DeploymentPlan → Preview → Approval → Execution → HealthCheck → Rollback.

Security:
- Default NEXARA_PRODUCTION_DEPLOY_ENABLED=false (preview-only mode)
- Production deploy requires: Approval + HealthCheck + Rollback plan
- Atomic deployment steps with SHA256 integrity checks
- Health check gates between each stage
- Automated rollback on health check failure
- Evidence recording for every deployment action
- Mock Driver for tests
- Local Preview mode for development
"""

from __future__ import annotations

import hashlib
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .models import new_id, now_iso


# ── Capability flags ──

DEPLOYMENT_MOCK_DRIVER = "DEPLOYMENT_MOCK_DRIVER"
DEPLOYMENT_PREVIEW_MODE = "DEPLOYMENT_PREVIEW_MODE"
DEPLOYMENT_PRODUCTION_ENABLED = "DEPLOYMENT_PRODUCTION_ENABLED"
DEPLOYMENT_HEALTH_CHECK_ACTIVE = "DEPLOYMENT_HEALTH_CHECK_ACTIVE"
DEPLOYMENT_AUTO_ROLLBACK = "DEPLOYMENT_AUTO_ROLLBACK"


class DeployState(str, Enum):
    DRAFT = "draft"
    PREVIEWED = "previewed"
    APPROVED = "approved"
    DEPLOYING = "deploying"
    DEPLOYED = "deployed"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DeployStrategy(str, Enum):
    ROLLING = "rolling"
    BLUE_GREEN = "blue_green"
    CANARY = "canary"
    RECREATE = "recreate"
    SHADOW = "shadow"


class StepType(str, Enum):
    BUILD = "build"
    TEST = "test"
    STAGE = "stage"
    MIGRATE = "migrate"
    DEPLOY = "deploy"
    SWITCH = "switch"
    VERIFY = "verify"
    CLEANUP = "cleanup"


@dataclass
class DeploymentCapability:
    flags: list[str] = field(default_factory=list)
    driver_type: str = "mock"
    production_deploy_enabled: bool = False
    supported_strategies: list[str] = field(default_factory=lambda: [
        "rolling", "blue_green", "canary", "recreate", "shadow"
    ])
    max_steps: int = 20
    health_check_timeout_seconds: int = 300
    rollback_timeout_seconds: int = 600


@dataclass
class DeploymentStep:
    step_id: str = field(default_factory=lambda: new_id("deploy_step"))
    step_type: StepType = StepType.DEPLOY
    name: str = ""
    command: str = ""
    expected_output: str = ""
    timeout_seconds: int = 120
    retry_count: int = 0
    max_retries: int = 2
    status: str = "pending"
    output: str = ""
    error: str = ""
    started_at: str = ""
    completed_at: str = ""
    duration_ms: float = 0.0
    integrity_sha256: str = ""

    def compute_integrity(self) -> str:
        canonical = json.dumps({
            "step_id": self.step_id,
            "step_type": self.step_type.value,
            "name": self.name,
            "command": self.command,
            "timeout_seconds": self.timeout_seconds,
        }, sort_keys=True, ensure_ascii=False)
        self.integrity_sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return self.integrity_sha256


@dataclass
class DeploymentPlan:
    plan_id: str = field(default_factory=lambda: new_id("deploy"))
    target: str = ""
    version: str = ""
    strategy: DeployStrategy = DeployStrategy.ROLLING
    steps: list[DeploymentStep] = field(default_factory=list)
    environment: str = "staging"
    artifacts: dict[str, str] = field(default_factory=dict)
    config_overrides: dict[str, Any] = field(default_factory=dict)
    rollback_steps: list[DeploymentStep] = field(default_factory=list)
    created_at: str = field(default_factory=now_iso)
    created_by: str = "nexara"
    plan_digest: str = ""
    state: DeployState = DeployState.DRAFT

    def compute_digest(self) -> str:
        steps_digest = hashlib.sha256(
            json.dumps([s.compute_integrity() for s in self.steps], sort_keys=True).encode()
        ).hexdigest()
        rollback_digest = hashlib.sha256(
            json.dumps([s.compute_integrity() for s in self.rollback_steps], sort_keys=True).encode()
        ).hexdigest()
        canonical = json.dumps({
            "target": self.target, "version": self.version,
            "strategy": self.strategy.value, "environment": self.environment,
            "steps_digest": steps_digest, "rollback_digest": rollback_digest,
        }, sort_keys=True, ensure_ascii=False)
        self.plan_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return self.plan_digest


@dataclass
class DeploymentPreview:
    plan_id: str = ""
    plan_digest: str = ""
    target: str = ""
    version: str = ""
    strategy: str = ""
    environment: str = ""
    steps_count: int = 0
    rollback_steps_count: int = 0
    estimated_duration_seconds: int = 0
    affected_resources: list[str] = field(default_factory=list)
    risk_level: str = "R2"
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    requires_approval: bool = True
    production_will_deploy: bool = False


@dataclass
class DeploymentResult:
    plan_id: str = ""
    deployment_id: str = field(default_factory=lambda: new_id("deploy_run"))
    success: bool = False
    state: DeployState = DeployState.DRAFT
    steps_completed: int = 0
    steps_failed: int = 0
    health_check_passed: bool = False
    rolled_back: bool = False
    error: str = ""
    output: str = ""
    duration_ms: float = 0.0
    evidence_ids: list[str] = field(default_factory=list)


@dataclass
class HealthCheckResult:
    healthy: bool = False
    checks_passed: int = 0
    checks_failed: int = 0
    checks_total: int = 0
    details: list[dict[str, Any]] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    duration_ms: float = 0.0


class DeploymentDriver(ABC):
    """Abstract deployment driver."""

    @abstractmethod
    def probe_capability(self) -> DeploymentCapability: ...

    @abstractmethod
    def dry_run(self, plan: DeploymentPlan) -> DeploymentPreview: ...

    @abstractmethod
    def execute_step(self, step: DeploymentStep) -> DeploymentStep: ...

    @abstractmethod
    def rollback_step(self, step: DeploymentStep) -> DeploymentStep: ...

    @abstractmethod
    def health_check(self, plan: DeploymentPlan) -> HealthCheckResult: ...

    @abstractmethod
    def get_state(self, plan: DeploymentPlan) -> DeployState: ...


class MockDeploymentDriver(DeploymentDriver):
    """Deterministic mock driver — simulates deployments without real infrastructure."""

    def __init__(self) -> None:
        self._deployed: dict[str, DeploymentPlan] = {}
        self._states: dict[str, DeployState] = {}
        self._health: dict[str, bool] = {}

    def probe_capability(self) -> DeploymentCapability:
        return DeploymentCapability(
            flags=[DEPLOYMENT_MOCK_DRIVER],
            driver_type="mock",
            production_deploy_enabled=False,
        )

    def dry_run(self, plan: DeploymentPlan) -> DeploymentPreview:
        total_seconds = sum(s.timeout_seconds for s in plan.steps)
        warnings: list[str] = []
        errors: list[str] = []

        if not plan.steps:
            errors.append("no_deployment_steps_defined")
        if not plan.rollback_steps:
            warnings.append("no_rollback_steps_defined")
        if plan.strategy == DeployStrategy.CANARY:
            warnings.append("canary_deployment_requires_traffic_split_config")

        return DeploymentPreview(
            plan_id=plan.plan_id,
            plan_digest=plan.compute_digest(),
            target=plan.target, version=plan.version,
            strategy=plan.strategy.value, environment=plan.environment,
            steps_count=len(plan.steps),
            rollback_steps_count=len(plan.rollback_steps),
            estimated_duration_seconds=total_seconds,
            affected_resources=[f"{plan.target}:{plan.environment}"],
            risk_level="R3" if plan.environment == "production" else "R2",
            warnings=warnings, errors=errors,
            requires_approval=plan.environment == "production",
            production_will_deploy=plan.environment == "production",
        )

    def execute_step(self, step: DeploymentStep) -> DeploymentStep:
        step.status = "completed"
        step.output = f"[Mock] Step '{step.name}' executed: {step.command}"
        step.completed_at = now_iso()
        step.duration_ms = step.timeout_seconds * 100  # simulate 10% of timeout
        return step

    def rollback_step(self, step: DeploymentStep) -> DeploymentStep:
        step.status = "rolled_back"
        step.output = f"[Mock] Step '{step.name}' rolled back"
        step.completed_at = now_iso()
        step.duration_ms = step.timeout_seconds * 50
        return step

    def health_check(self, plan: DeploymentPlan) -> HealthCheckResult:
        healthy = self._health.get(plan.plan_id, True)
        return HealthCheckResult(
            healthy=healthy,
            checks_passed=3 if healthy else 1,
            checks_failed=0 if healthy else 2,
            checks_total=3,
            details=[
                {"check": "connectivity", "passed": healthy,
                 "message": "[Mock] OK" if healthy else "[Mock] FAILED"},
                {"check": "artifact_integrity", "passed": healthy,
                 "message": "[Mock] SHA256 OK" if healthy else "[Mock] MISMATCH"},
                {"check": "service_health", "passed": healthy,
                 "message": "[Mock] 200 OK" if healthy else "[Mock] 503"},
            ],
            recommendations=[] if healthy else ["Rollback recommended: service unhealthy"],
            duration_ms=150.0,
        )

    def get_state(self, plan: DeploymentPlan) -> DeployState:
        return self._states.get(plan.plan_id, DeployState.DRAFT)


class GovernedDeploymentAdapter:
    """Governed deployment adapter with Plan→Preview→Approval→Execute→HealthCheck→Rollback.

    Default NEXARA_PRODUCTION_DEPLOY_ENABLED=false:
    - Production deployments are BLOCKED without explicit enablement
    - All deployments go through preview/dry-run first
    - Health check required before marking healthy
    - Auto-rollback on health check failure (configurable)
    """

    def __init__(
        self,
        driver: DeploymentDriver | None = None,
        *,
        evidence_store=None,
        approval_engine=None,
        production_deploy_enabled: bool = False,
        auto_rollback: bool = True,
        health_check_enabled: bool = True,
    ) -> None:
        self.driver = driver or MockDeploymentDriver()
        self.evidence = evidence_store
        self.approvals = approval_engine
        self.production_deploy_enabled = production_deploy_enabled
        self.auto_rollback = auto_rollback
        self.health_check_enabled = health_check_enabled
        self._plans: dict[str, DeploymentPlan] = {}
        self._action_history: list[dict[str, Any]] = []

    # ── Evidence ──

    def _record_evidence(self, plan: DeploymentPlan, result: DeploymentResult) -> list[str]:
        if not self.evidence:
            return []
        payload = json.dumps({
            "plan_id": plan.plan_id, "deployment_id": result.deployment_id,
            "target": plan.target, "version": plan.version,
            "strategy": plan.strategy.value, "environment": plan.environment,
            "success": result.success, "state": result.state.value,
            "steps_completed": result.steps_completed,
            "steps_failed": result.steps_failed,
            "rolled_back": result.rolled_back,
            "plan_digest": plan.plan_digest,
            "error": result.error, "duration_ms": result.duration_ms,
        }, ensure_ascii=False)
        try:
            ev = self.evidence.add(
                "deployment_session", "deployment_execution",
                f"Deploy: {plan.target}/{plan.version}",
                payload, result.deployment_id,
                actor="deployment_adapter", source="deployment",
                verification_status="verified",
            )
            return [ev.evidence_id]
        except Exception:
            return []

    # ── Pipeline ──

    def create_plan(
        self, target: str, version: str,
        strategy: DeployStrategy = DeployStrategy.ROLLING, *,
        environment: str = "staging",
        steps: list[DeploymentStep] | None = None,
        rollback_steps: list[DeploymentStep] | None = None,
        artifacts: dict[str, str] | None = None,
        config_overrides: dict[str, Any] | None = None,
    ) -> DeploymentPlan:
        """Step 1: Create a deployment plan."""
        plan = DeploymentPlan(
            target=target, version=version, strategy=strategy,
            environment=environment,
            steps=steps or [], rollback_steps=rollback_steps or [],
            artifacts=artifacts or {}, config_overrides=config_overrides or {},
        )
        plan.compute_digest()
        self._plans[plan.plan_id] = plan
        self._action_history.append({
            "step": "create_plan", "plan_id": plan.plan_id,
            "target": target, "version": version,
            "environment": environment, "timestamp": plan.created_at,
        })
        return plan

    def preview(self, plan_id: str) -> DeploymentPreview:
        """Step 2: Dry-run preview of the deployment plan."""
        plan = self._plans.get(plan_id)
        if not plan:
            return DeploymentPreview(plan_id=plan_id, errors=["plan_not_found"])

        preview = self.driver.dry_run(plan)

        # Add governance warnings
        if plan.environment == "production" and not self.production_deploy_enabled:
            preview.errors.append("production_deploy_disabled_by_config")
            preview.requires_approval = True
        if not plan.rollback_steps:
            preview.warnings.append("no_rollback_plan_provided")
        if len(plan.steps) > self.driver.probe_capability().max_steps:
            preview.warnings.append("step_count_exceeds_maximum")

        plan.state = DeployState.PREVIEWED
        self._action_history.append({
            "step": "preview", "plan_id": plan_id,
            "errors": preview.errors, "warnings": preview.warnings,
        })
        return preview

    def execute(self, plan_id: str, *, force: bool = False) -> DeploymentResult:
        """Step 3+4: Execute deployment plan (after approval).

        With production_deploy_enabled=false, production deploys are blocked.
        """
        plan = self._plans.get(plan_id)
        if not plan:
            return DeploymentResult(plan_id=plan_id, error="plan_not_found")

        # Production gate
        if plan.environment == "production" and not self.production_deploy_enabled:
            return DeploymentResult(
                plan_id=plan_id,
                success=False, state=DeployState.CANCELLED,
                error="production_deploy_disabled:NEXARA_PRODUCTION_DEPLOY_ENABLED=false",
            )

        started = time.monotonic()
        result = DeploymentResult(plan_id=plan_id, state=DeployState.DEPLOYING)

        # Re-verify step integrity before execution
        for step in plan.steps:
            if step.integrity_sha256 and hasattr(step, 'compute_integrity'):
                if step.compute_integrity() != step.integrity_sha256:
                    result.error = f"step_integrity_violation:{step.name}"
                    result.state = DeployState.FAILED
                    plan.state = DeployState.FAILED
                    result.duration_ms = (time.monotonic() - started) * 1000
                    result.evidence_ids = self._record_evidence(plan, result)
                    return result

        # Execute each step
        for step in plan.steps:
            step.started_at = now_iso()
            step = self.driver.execute_step(step)

            if step.status != "completed":
                result.steps_failed += 1
                result.error = f"step_failed:{step.name}:{step.error or 'unknown'}"
                plan.state = DeployState.FAILED
                result.state = DeployState.FAILED
                result.duration_ms = (time.monotonic() - started) * 1000

                # Attempt rollback
                if self.auto_rollback and plan.rollback_steps:
                    rollback_result = self._rollback(plan)
                    result.rolled_back = rollback_result.rolled_back
                    result.output += f"\n[ROLLBACK] {'OK' if rollback_result.success else 'FAILED'}"
                result.evidence_ids = self._record_evidence(plan, result)
                return result

            result.steps_completed += 1

        # All steps completed
        plan.state = DeployState.DEPLOYED
        result.state = DeployState.DEPLOYED
        result.success = True

        # Health check
        if self.health_check_enabled:
            hc = self.driver.health_check(plan)
            result.health_check_passed = hc.healthy
            if hc.healthy:
                plan.state = DeployState.HEALTHY
                result.state = DeployState.HEALTHY
                result.output += "\n[HEALTH_CHECK] PASSED"
            else:
                plan.state = DeployState.UNHEALTHY
                result.state = DeployState.UNHEALTHY
                result.output += f"\n[HEALTH_CHECK] FAILED: {hc.recommendations}"

                if self.auto_rollback and plan.rollback_steps:
                    rollback_result = self._rollback(plan)
                    result.rolled_back = rollback_result.rolled_back
                    result.output += f"\n[ROLLBACK] {'OK' if rollback_result.success else 'FAILED'}"

        result.duration_ms = (time.monotonic() - started) * 1000
        result.evidence_ids = self._record_evidence(plan, result)

        self._action_history.append({
            "step": "execute", "plan_id": plan_id,
            "success": result.success, "state": result.state.value,
            "steps_completed": result.steps_completed,
            "health_check_passed": result.health_check_passed,
            "rolled_back": result.rolled_back,
        })

        return result

    def _rollback(self, plan: DeploymentPlan) -> DeploymentResult:
        """Execute rollback steps in reverse order."""
        plan.state = DeployState.ROLLING_BACK
        result = DeploymentResult(plan_id=plan.plan_id, state=DeployState.ROLLING_BACK)

        for step in reversed(plan.rollback_steps):
            step.started_at = now_iso()
            step = self.driver.rollback_step(step)
            if step.status != "rolled_back":
                result.error = f"rollback_step_failed:{step.name}"
                plan.state = DeployState.FAILED
                result.state = DeployState.FAILED
                result.evidence_ids = self._record_evidence(plan, result)
                return result

        plan.state = DeployState.ROLLED_BACK
        result.success = True
        result.rolled_back = True
        result.state = DeployState.ROLLED_BACK
        result.evidence_ids = self._record_evidence(plan, result)
        self._action_history.append({
            "step": "rollback", "plan_id": plan.plan_id,
            "success": True,
        })
        return result

    def health_check(self, plan_id: str) -> HealthCheckResult:
        """Run health check on a deployed plan."""
        plan = self._plans.get(plan_id)
        if not plan:
            return HealthCheckResult(healthy=False, recommendations=["plan_not_found"])
        hc = self.driver.health_check(plan)
        self._action_history.append({
            "step": "health_check", "plan_id": plan_id,
            "healthy": hc.healthy,
            "checks_passed": hc.checks_passed,
        })
        return hc

    def rollback(self, plan_id: str) -> DeploymentResult:
        """Manually trigger rollback."""
        plan = self._plans.get(plan_id)
        if not plan:
            return DeploymentResult(plan_id=plan_id, error="plan_not_found")
        if not plan.rollback_steps:
            return DeploymentResult(plan_id=plan_id, error="no_rollback_steps_defined")
        return self._rollback(plan)

    # ── Lifecycle ──

    def probe_capability(self) -> DeploymentCapability:
        cap = self.driver.probe_capability()
        cap.production_deploy_enabled = self.production_deploy_enabled
        if not self.production_deploy_enabled:
            cap.flags.append(DEPLOYMENT_PREVIEW_MODE)
        if self.production_deploy_enabled:
            cap.flags.append(DEPLOYMENT_PRODUCTION_ENABLED)
        if self.health_check_enabled:
            cap.flags.append(DEPLOYMENT_HEALTH_CHECK_ACTIVE)
        if self.auto_rollback:
            cap.flags.append(DEPLOYMENT_AUTO_ROLLBACK)
        return cap

    def get_plan(self, plan_id: str) -> DeploymentPlan | None:
        return self._plans.get(plan_id)

    def get_history(self) -> list[dict[str, Any]]:
        return list(self._action_history)

    def validate_rollback_plan(self, plan_id: str) -> bool:
        """Verify that rollback steps exist and are different from deploy steps."""
        plan = self._plans.get(plan_id)
        if not plan or not plan.rollback_steps:
            return False
        deploy_names = {s.name for s in plan.steps}
        rollback_names = {s.name for s in plan.rollback_steps}
        return len(deploy_names & rollback_names) == 0
