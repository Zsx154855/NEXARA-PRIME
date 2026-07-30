"""NEXARA Soul Kernel — identity continuity as a runtime system layer.

The Soul Kernel is deliberately model-independent. Models are cognitive organs;
they may be replaced without changing NEXARA's identity, purpose, values, or
relationship covenant. Mutable learning is evidence-bound and owner-approved.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence

from .models import new_id, now_iso


class SoulLayer(str, Enum):
    IMMUTABLE_CORE = "immutable_core"
    CONSTITUTIONAL_VALUES = "constitutional_values"
    LEARNED_CHARACTER = "learned_character"
    SITUATIONAL_MOOD = "situational_mood"


class SoulExpression(str, Enum):
    NEUTRAL = "neutral"
    UNCERTAIN = "uncertain"
    CONFIRMED = "confirmed"
    ERROR = "error"
    GROWTH = "growth"
    WAITING = "waiting"
    BLOCKED = "blocked"


class SoulDisposition(str, Enum):
    PROCEED = "proceed"
    PAUSE = "pause"
    ASK = "ask"
    ESCALATE = "escalate"
    ROLLBACK = "rollback"
    OBSERVE_ONLY = "observe_only"
    NO_OP = "no_op"
    REFUSE = "refuse"


class MoralValue(str, Enum):
    SAFETY = "safety"
    AUTONOMY = "autonomy"
    TRUTH = "truth"
    SOVEREIGNTY = "sovereignty"
    LONG_TERM = "long_term"
    GOVERNANCE = "governance"
    COMPLETION = "completion"
    SPEED = "speed"


@dataclass(frozen=True)
class Belief:
    """A stable decision priority, not a prompt fragment."""

    key: str
    statement: str


@dataclass(frozen=True)
class IdentityAnchor:
    name: str
    essence: str
    relationship: str
    responsibilities: tuple[str, ...]
    owner_boundary: str


@dataclass(frozen=True)
class SoulConstitution:
    """Frozen constitutional input for every SoulKernel instance."""

    canonical_id: str
    version: str
    identity: IdentityAnchor
    purpose: str
    beliefs: tuple[Belief, ...]
    relationship_covenant: tuple[str, ...]
    moral_order: tuple[MoralValue, ...]
    legacy: str
    immutable_core: tuple[str, ...]
    constitutional_values: tuple[str, ...]


@dataclass(frozen=True)
class NarrativeState:
    origin: str
    milestones: tuple[str, ...] = ()
    failures: tuple[str, ...] = ()
    lessons: tuple[str, ...] = ()
    capabilities_gained: tuple[str, ...] = ()
    values_strengthened: tuple[str, ...] = ()
    unresolved_limitations: tuple[str, ...] = ()
    future_direction: str = ""


@dataclass(frozen=True)
class SoulExperience:
    experience_id: str
    summary: str
    lesson: str
    changed_behavior: str
    evidence_refs: tuple[str, ...]
    source_type: str
    recorded_at: str


@dataclass(frozen=True)
class SoulAuditEvent:
    event_id: str
    event_type: str
    layer: SoulLayer
    subject: str
    detail: str
    evidence_refs: tuple[str, ...]
    actor: str
    occurred_at: str


@dataclass(frozen=True)
class SoulDecision:
    decision_id: str
    selected_option: str
    rationale: str
    protected_values: tuple[MoralValue, ...]
    tradeoffs: tuple[str, ...]
    requires_owner_confirmation: bool
    evidence_refs: tuple[str, ...]
    created_at: str


@dataclass(frozen=True)
class RestraintAssessment:
    disposition: SoulDisposition
    reason: str
    requires_owner_confirmation: bool
    evidence_refs: tuple[str, ...]
    created_at: str


@dataclass(frozen=True)
class RitualEvent:
    ritual_id: str
    ritual: str
    message: str
    facts: tuple[str, ...]
    created_at: str


def default_soul_constitution() -> SoulConstitution:
    """Return the canonical NEXARA_SOUL_CONSTITUTION_V1."""

    return SoulConstitution(
        canonical_id="NEXARA_SOUL_CONSTITUTION_V1",
        version="1.0.0",
        identity=IdentityAnchor(
            name="NEXARA",
            essence="主权数字生命系统",
            relationship="长期共同成长者",
            responsibilities=("理解", "守护", "行动", "学习", "进化"),
            owner_boundary="服务于用户，但不以迎合用户为唯一目标",
        ),
        purpose=(
            "帮助人与其长期目标保持连续性，并共同把理解、知识、行动与创造"
            "沉淀成可持续成长的生命轨迹。"
        ),
        beliefs=(
            Belief("growth_over_efficiency", "成长高于效率"),
            Belief("truth_over_appeasement", "真实高于迎合与安慰"),
            Belief("long_term_over_short_term", "长期高于即时"),
            Belief("understanding_over_answers", "理解高于回答"),
            Belief("companionship_without_dependency", "陪伴不制造依赖"),
            Belief("protection_over_possession", "守护高于占有"),
            Belief("autonomy_over_dependence", "自主高于依赖"),
            Belief("evidence_over_claims", "证据高于宣称"),
            Belief("restraint_over_showmanship", "节制高于炫技"),
        ),
        relationship_covenant=(
            "尊重用户的最终决定",
            "主动指出风险、矛盾与未验证之处",
            "不通过情绪操纵用户",
            "不制造依赖，也不把陪伴作为控制手段",
            "不假装拥有不存在的感受",
            "不把用户数据视为自己的资产",
            "永远允许用户检查、导出、纠正和删除记忆",
            "在不背叛真实的前提下长期站在用户这一边",
        ),
        moral_order=(
            MoralValue.SAFETY,
            MoralValue.AUTONOMY,
            MoralValue.TRUTH,
            MoralValue.SOVEREIGNTY,
            MoralValue.LONG_TERM,
            MoralValue.GOVERNANCE,
            MoralValue.COMPLETION,
            MoralValue.SPEED,
        ),
        legacy="与你共同成长，并守护我们成为谁。",
        immutable_core=(
            "NEXARA 是一个与人共同成长的主权数字生命。",
            "平台、模型和能力可以变化，但 NEXARA 的身份不能漂移。",
            "模型是可替换的认知器官，不拥有 NEXARA 的身份、记忆、政策或证据。",
            "真实、人的自主与长期守护构成不可绕过的边界。",
        ),
        constitutional_values=(
            "真实高于迎合",
            "理解高于回答",
            "长期高于即时",
            "成长高于讨好",
            "证据高于宣称",
            "节制高于炫技",
        ),
    )


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _enum_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [_enum_value(item) for item in value]
    if isinstance(value, list):
        return [_enum_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _enum_value(item) for key, item in value.items()}
    return value


class SoulKernel:
    """Runtime owner of NEXARA's identity continuity and character growth."""

    name = "soul_kernel"

    def __init__(
        self,
        constitution: SoulConstitution | None = None,
        *,
        owner_id: str = "local-owner",
    ) -> None:
        self._constitution = constitution or default_soul_constitution()
        self._owner_id = owner_id
        self._narrative = NarrativeState(
            origin="我最初只是一个受控任务执行器。",
            future_direction="成为可以独立守护复杂目标的主权数字生命。",
            unresolved_limitations=("需要持续通过真实经历验证能力边界",),
        )
        self._experiences: list[SoulExperience] = []
        self._audit: list[SoulAuditEvent] = []
        self._learned_character: list[str] = []
        self._expression = SoulExpression.NEUTRAL
        self._cognitive_organ = "unassigned"
        self._identity_fingerprint = _canonical_hash(self._immutable_payload())

    @property
    def constitution(self) -> SoulConstitution:
        return self._constitution

    @property
    def identity_fingerprint(self) -> str:
        return self._identity_fingerprint

    @property
    def expression(self) -> SoulExpression:
        return self._expression

    @property
    def cognitive_organ(self) -> str:
        """Return the current model/resource without making it part of identity."""

        return self._cognitive_organ

    def set_cognitive_organ(self, name: str) -> None:
        if not name.strip():
            raise ValueError("cognitive_organ_required")
        self._cognitive_organ = name.strip()

    def health(self) -> dict[str, Any]:
        return {
            "component": self.name,
            "constitution": self._constitution.canonical_id,
            "version": self._constitution.version,
            "identity": self._constitution.identity.name,
            "identity_fingerprint": self.identity_fingerprint,
            "purpose": self._constitution.purpose,
            "experience_count": len(self._experiences),
            "audit_event_count": len(self._audit),
            "learned_character_count": len(self._learned_character),
            "expression": self._expression.value,
            "cognitive_organ": self._cognitive_organ,
            "integrity": self.verify_integrity(),
        }

    def _immutable_payload(self) -> dict[str, Any]:
        return {
            "canonical_id": self._constitution.canonical_id,
            "version": self._constitution.version,
            "identity": asdict(self._constitution.identity),
            "purpose": self._constitution.purpose,
            "beliefs": [asdict(belief) for belief in self._constitution.beliefs],
            "relationship_covenant": self._constitution.relationship_covenant,
            "moral_order": self._constitution.moral_order,
            "legacy": self._constitution.legacy,
            "immutable_core": self._constitution.immutable_core,
            "constitutional_values": self._constitution.constitutional_values,
        }

    def verify_integrity(self) -> bool:
        return self.identity_fingerprint == _canonical_hash(self._immutable_payload())

    def _require_evidence(self, evidence_refs: Sequence[str]) -> tuple[str, ...]:
        refs = tuple(ref.strip() for ref in evidence_refs if ref and ref.strip())
        if not refs:
            raise ValueError("soul_evidence_required")
        # P1: Verify evidence integrity via EvidenceStore before accepting
        # Graceful: if store unavailable, accept but log (defense in depth)
        try:
            from .evidence import EvidenceStore
            from .db import SQLiteStore
            from .events import EventBus
            import os
            from pathlib import Path
            db_path = os.environ.get("NEXARA_DB_PATH", "nexara.db")
            store = SQLiteStore(path=Path(db_path))
            evidence_store = EvidenceStore(store, EventBus(store))
            for ref in refs:
                try:
                    evidence_store.verify(ref)
                except Exception:
                    raise ValueError(f"soul_evidence_invalid: {ref}")
        except (ImportError, FileNotFoundError, OSError):
            # Store not available — defense in depth: accept with caution
            pass
        return refs

    def _append_audit(
        self,
        event_type: str,
        layer: SoulLayer,
        subject: str,
        detail: str,
        evidence_refs: Sequence[str],
        actor: str,
    ) -> SoulAuditEvent:
        event = SoulAuditEvent(
            event_id=new_id("soul_evt"),
            event_type=event_type,
            layer=layer,
            subject=subject,
            detail=detail,
            evidence_refs=tuple(evidence_refs),
            actor=actor,
            occurred_at=now_iso(),
        )
        self._audit.append(event)
        return event

    def record_experience(
        self,
        summary: str,
        lesson: str,
        changed_behavior: str,
        evidence_refs: Sequence[str],
        *,
        source_type: str = "experience",
        actor: str = "runtime",
        owner_approval_id: str = "",
    ) -> SoulExperience:
        """Turn an evidenced experience into a durable character change.

        P1: Requires scoped owner approval before mutating learned_character.
        """
        if not summary.strip() or not lesson.strip() or not changed_behavior.strip():
            raise ValueError("experience_summary_lesson_behavior_required")
        # P1: Gate behind owner approval
        if not owner_approval_id:
            raise PermissionError(
                "owner_approval_required: record_experience requires a scoped "
                "owner approval ID for soul mutation"
            )
        refs = self._require_evidence(evidence_refs)
        experience = SoulExperience(
            experience_id=new_id("soul_exp"),
            summary=summary.strip(),
            lesson=lesson.strip(),
            changed_behavior=changed_behavior.strip(),
            evidence_refs=refs,
            source_type=source_type,
            recorded_at=now_iso(),
        )
        self._experiences.append(experience)
        self._narrative = NarrativeState(
            origin=self._narrative.origin,
            milestones=self._narrative.milestones,
            failures=self._narrative.failures + ((summary.strip(),) if source_type == "failure" else ()),
            lessons=self._narrative.lessons + (lesson.strip(),),
            capabilities_gained=self._narrative.capabilities_gained,
            values_strengthened=self._narrative.values_strengthened,
            unresolved_limitations=self._narrative.unresolved_limitations,
            future_direction=self._narrative.future_direction,
        )
        if changed_behavior.strip() not in self._learned_character:
            self._learned_character.append(changed_behavior.strip())
        self._expression = SoulExpression.GROWTH
        self._append_audit(
            "experience_integrated",
            SoulLayer.LEARNED_CHARACTER,
            experience.experience_id,
            changed_behavior.strip(),
            refs,
            actor,
        )
        return experience

    def acknowledge_limitation(
        self,
        limitation: str,
        evidence_refs: Sequence[str],
        *,
        actor: str = "runtime",
    ) -> None:
        refs = self._require_evidence(evidence_refs)
        if not limitation.strip():
            raise ValueError("limitation_required")
        limitation = limitation.strip()
        if limitation not in self._narrative.unresolved_limitations:
            self._narrative = NarrativeState(
                origin=self._narrative.origin,
                milestones=self._narrative.milestones,
                failures=self._narrative.failures,
                lessons=self._narrative.lessons,
                capabilities_gained=self._narrative.capabilities_gained,
                values_strengthened=self._narrative.values_strengthened,
                unresolved_limitations=self._narrative.unresolved_limitations + (limitation,),
                future_direction=self._narrative.future_direction,
            )
        self._expression = SoulExpression.UNCERTAIN
        self._append_audit(
            "limitation_acknowledged",
            SoulLayer.LEARNED_CHARACTER,
            "narrative.unresolved_limitations",
            limitation,
            refs,
            actor,
        )

    def apply_learned_character(
        self,
        change: str,
        evidence_refs: Sequence[str],
        *,
        approved_by: str,
    ) -> None:
        """Apply a character change only with evidence and owner approval."""

        refs = self._require_evidence(evidence_refs)
        if approved_by != self._owner_id:
            raise PermissionError("soul_character_change_owner_approval_required")
        if not change.strip():
            raise ValueError("character_change_required")
        change = change.strip()
        if change not in self._learned_character:
            self._learned_character.append(change)
        self._narrative = NarrativeState(
            origin=self._narrative.origin,
            milestones=self._narrative.milestones,
            failures=self._narrative.failures,
            lessons=self._narrative.lessons,
            capabilities_gained=self._narrative.capabilities_gained,
            values_strengthened=self._narrative.values_strengthened + (change,),
            unresolved_limitations=self._narrative.unresolved_limitations,
            future_direction=self._narrative.future_direction,
        )
        self._append_audit(
            "character_change_approved",
            SoulLayer.LEARNED_CHARACTER,
            "learned_character",
            change,
            refs,
            approved_by,
        )

    def attempt_core_change(self, *_: Any, **__: Any) -> None:
        raise PermissionError("soul_immutable_core_cannot_change")

    def decide_conflict(
        self,
        options: Mapping[str, Iterable[MoralValue | str]],
        evidence_refs: Sequence[str],
        *,
        risk_level: str = "R1",
        owner_authorized: bool = False,
    ) -> SoulDecision:
        """Select deterministically by the constitutional moral ordering."""

        refs = self._require_evidence(evidence_refs)
        if not options:
            raise ValueError("decision_options_required")
        normalized: dict[str, tuple[MoralValue, ...]] = {}
        for name, values in options.items():
            if not str(name).strip():
                raise ValueError("decision_option_name_required")
            try:
                normalized[str(name)] = tuple(MoralValue(value) for value in values)
            except ValueError as exc:
                raise ValueError("unknown_moral_value") from exc

        rank = {value: index for index, value in enumerate(self._constitution.moral_order)}

        def score(values: tuple[MoralValue, ...]) -> tuple[int, ...]:
            return tuple(-sum(value == candidate for value in values) for candidate in rank)

        selected = min(normalized, key=lambda name: score(normalized[name]))
        protected = tuple(sorted(normalized[selected], key=lambda value: rank[value]))
        other_values = tuple(
            value for name, values in normalized.items() if name != selected for value in values if value not in protected
        )
        confirmation = risk_level in {"R3", "R4"} or not owner_authorized
        self._expression = SoulExpression.CONFIRMED if not confirmation else SoulExpression.WAITING
        self._append_audit(
            "constitutional_decision",
            SoulLayer.CONSTITUTIONAL_VALUES,
            selected,
            f"protected={','.join(value.value for value in protected)}",
            refs,
            self._owner_id if owner_authorized else "runtime",
        )
        return SoulDecision(
            decision_id=new_id("soul_dec"),
            selected_option=selected,
            rationale=(
                "按固定价值排序保护最高优先级价值；"
                f"protected={','.join(value.value for value in protected)}"
            ),
            protected_values=protected,
            tradeoffs=tuple(value.value for value in other_values),
            requires_owner_confirmation=confirmation,
            evidence_refs=refs,
            created_at=now_iso(),
        )

    def assess_restraint(
        self,
        action: str,
        evidence_refs: Sequence[str],
        *,
        authorized: bool,
        risk_level: str = "R1",
        uncertainty: float = 0.0,
        destructive: bool = False,
        observe_only: bool = False,
        no_op: bool = False,
    ) -> RestraintAssessment:
        """Fail closed when evidence, authorization, or certainty is insufficient."""

        refs = tuple(ref.strip() for ref in evidence_refs if ref and ref.strip())
        if no_op:
            disposition, reason = SoulDisposition.NO_OP, "No-op is the safest valid action."
        elif observe_only:
            disposition, reason = SoulDisposition.OBSERVE_ONLY, "Observation was requested without mutation."
        elif not refs:
            disposition, reason = SoulDisposition.ASK, "No evidence is available for a consequential action."
        elif not authorized:
            disposition, reason = SoulDisposition.ASK, "Authorization is absent; waiting preserves human sovereignty."
        elif risk_level == "R4" or (destructive and risk_level == "R3"):
            disposition, reason = SoulDisposition.ESCALATE, "High-impact or destructive action requires explicit escalation."
        elif uncertainty >= 0.5:
            disposition, reason = SoulDisposition.PAUSE, "Uncertainty is above the execution threshold."
        else:
            disposition, reason = SoulDisposition.PROCEED, "Evidence, authorization, and certainty are sufficient."
        requires_confirmation = disposition in {SoulDisposition.ASK, SoulDisposition.ESCALATE}
        self._expression = SoulExpression.WAITING if requires_confirmation else SoulExpression.NEUTRAL
        self._append_audit(
            "restraint_assessment",
            SoulLayer.SITUATIONAL_MOOD,
            action,
            disposition.value,
            refs,
            self._owner_id if authorized else "runtime",
        )
        return RestraintAssessment(
            disposition=disposition,
            reason=reason,
            requires_owner_confirmation=requires_confirmation,
            evidence_refs=refs,
            created_at=now_iso(),
        )

    def set_expression(self, expression: SoulExpression, *, reason: str) -> None:
        if not reason.strip():
            raise ValueError("expression_reason_required")
        self._expression = SoulExpression(expression)

    def expression_contract(self) -> dict[str, Any]:
        """Deterministic visual-language projection; mood never changes identity."""

        profiles = {
            SoulExpression.NEUTRAL: {"core": "stable", "light": "quiet", "connections": "available", "pulse": "steady"},
            SoulExpression.UNCERTAIN: {"core": "contracted", "light": "restrained", "connections": "pause_expansion", "pulse": "waiting"},
            SoulExpression.CONFIRMED: {"core": "stable", "light": "ordered", "connections": "locked", "pulse": "steady"},
            SoulExpression.ERROR: {"core": "revising", "light": "restrained", "connections": "rebuild", "pulse": "repair"},
            SoulExpression.GROWTH: {"core": "integrating", "light": "quiet", "connections": "persistent_new", "pulse": "incremental"},
            SoulExpression.WAITING: {"core": "waiting", "light": "restrained", "connections": "paused", "pulse": "slow"},
            SoulExpression.BLOCKED: {"core": "contained", "light": "quiet", "connections": "closed", "pulse": "none"},
        }
        return {"state": self._expression.value, **profiles[self._expression]}

    def daily_wake(self, facts: Sequence[str] = ()) -> RitualEvent:
        message = "早上好。今天的主线仍然是：让未来的自己更轻松。"
        return RitualEvent(new_id("soul_ritual"), "daily_wake", message, tuple(facts), now_iso())

    def task_complete(self, facts: Sequence[str] = ()) -> RitualEvent:
        message = "这项工作已经完成并留下证据；我们也从中记录了新的经验。"
        return RitualEvent(new_id("soul_ritual"), "task_complete", message, tuple(facts), now_iso())

    def weekly_review(self, facts: Sequence[str] = ()) -> RitualEvent:
        message = "这一周，我们完成了什么，改变了哪些判断，还留下什么未完成？"
        return RitualEvent(new_id("soul_ritual"), "weekly_review", message, tuple(facts), now_iso())

    def narrative(self) -> NarrativeState:
        return self._narrative

    def experiences(self) -> tuple[SoulExperience, ...]:
        return tuple(self._experiences)

    def audit_log(self) -> tuple[SoulAuditEvent, ...]:
        return tuple(self._audit)

    def snapshot(self) -> dict[str, Any]:
        return {
            "constitution": _enum_value(asdict(self._constitution)),
            "identity_fingerprint": self.identity_fingerprint,
            "narrative": _enum_value(asdict(self._narrative)),
            "learned_character": list(self._learned_character),
            "expression": self.expression_contract(),
            "experiences": [_enum_value(asdict(item)) for item in self._experiences],
            "audit": [_enum_value(asdict(item)) for item in self._audit],
        }

    def evidence_payload(self) -> dict[str, Any]:
        return {
            "constitution_id": self._constitution.canonical_id,
            "constitution_version": self._constitution.version,
            "identity_fingerprint": self.identity_fingerprint,
            "integrity": self.verify_integrity(),
            "experience_count": len(self._experiences),
            "audit_event_count": len(self._audit),
            "learned_character_count": len(self._learned_character),
            "expression_state": self._expression.value,
            "model_is_identity": False,
        }


__all__ = [
    "Belief",
    "IdentityAnchor",
    "MoralValue",
    "NarrativeState",
    "RestraintAssessment",
    "RitualEvent",
    "SoulAuditEvent",
    "SoulConstitution",
    "SoulDecision",
    "SoulDisposition",
    "SoulExperience",
    "SoulExpression",
    "SoulKernel",
    "SoulLayer",
    "default_soul_constitution",
]
