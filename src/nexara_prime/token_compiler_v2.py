from __future__ import annotations

import hashlib
from typing import Any

from .models import (
    CompiledPrompt,
    MissionSpec,
    TokenCompilationRecord,
    new_id,
    now_iso,
)


class TokenCompilerV2:
    """Enhanced token compiler with progressive disclosure and deduplication.

    Features:
    - shared_immutable_context: context shared by all roles
    - role_specific_slices: only what each role needs
    - progressive_disclosure: load more context on demand
    - summary_cache: cache compiled summaries
    - object_references: bounded object references
    - evidence_references: reference evidence without embedding
    - context_deduplication: remove redundant context items
    - Token estimation: ~4 chars per token
    """

    def __init__(self) -> None:
        self._summary_cache: dict[str, str] = {}
        self._disclosure_levels: dict[str, int] = {}

    # ── Main Compilation ────────────────────────────────────────────

    def compile_with_references(
        self,
        mission_spec: MissionSpec,
        context: dict[str, Any],
        roles: list[str],
        capabilities: list[str],
        evidence_refs: list[str] | None = None,
        skill_refs: list[str] | None = None,
    ) -> tuple[CompiledPrompt, TokenCompilationRecord]:
        """Compile a prompt with progressive disclosure, deduplication,
        and reference-based context loading.

        Returns (CompiledPrompt, TokenCompilationRecord).
        """
        evidence_refs = evidence_refs or []
        skill_refs = skill_refs or []

        # ── 1. Build shared immutable context ──
        shared_immutable: dict[str, Any] = {
            "mission_id": mission_spec.mission_id,
            "title": mission_spec.title,
            "objective": mission_spec.objective,
            "boundaries": mission_spec.boundaries,
            "constraints": mission_spec.constraints,
            "deliverables": mission_spec.deliverables,
            "acceptance_criteria": mission_spec.acceptance_criteria,
            "risk_level": (
                mission_spec.risk_level.value
                if hasattr(mission_spec.risk_level, "value")
                else str(mission_spec.risk_level)
            ),
            "source_dir": mission_spec.source_dir,
        }

        # ── 2. Create role-specific slices (progressive disclosure) ──
        role_specific_slices: dict[str, str] = {}
        for role in roles:
            role_lower = role.lower()
            slice_parts: list[str] = []

            # Every role gets boundaries and constraints from shared context
            slice_parts.append(
                f"Boundaries: {'; '.join(mission_spec.boundaries) or 'None stated'}"
            )
            slice_parts.append(
                f"Constraints: {'; '.join(mission_spec.constraints) or 'None stated'}"
            )

            # Executor gets deliverables and context
            if role_lower in ("executor", "orchestrator"):
                slice_parts.append(
                    f"Deliverables: {'; '.join(mission_spec.deliverables) or 'None stated'}"
                )
                slice_parts.append(
                    f"Acceptance: {'; '.join(mission_spec.acceptance_criteria) or 'Produce verifiable evidence'}"
                )

            # Planner gets full objective + context
            if role_lower == "planner":
                slice_parts.append(f"Full objective: {mission_spec.objective}")
                slice_parts.append(
                    f"Risks: {'; '.join(mission_spec.risks) or 'None identified'}"
                )

            # Reviewer/Auditor gets risk + constraints
            if role_lower in ("reviewer", "auditor"):
                slice_parts.append(
                    f"Risk level: {mission_spec.risk_level.value if hasattr(mission_spec.risk_level, 'value') else mission_spec.risk_level}"
                )
                slice_parts.append(
                    f"Risks: {'; '.join(mission_spec.risks) or 'None identified'}"
                )

            # Researcher gets source_dir and contextual hints
            if role_lower == "researcher":
                if mission_spec.source_dir:
                    slice_parts.append(f"Source: {mission_spec.source_dir}")
                slice_parts.append(f"Objective: {mission_spec.objective[:500]}")

            role_specific_slices[role] = "\n".join(slice_parts)

        # ── 3. Progressive disclosure levels ──
        disclosure_system: dict[int, str] = {
            0: "Minimal context. Answer directly or request more context.",
            1: "Standard context. Mission objective, boundaries, and constraints are available.",
            2: "Full context. All mission spec fields, evidence references, and skill references are loaded.",
            3: "Archival context. Full mission history, all past evidence, and complete workspace state.",
        }

        # Start at level 1 for most roles, level 2 for complex missions
        initial_disclosure = 2 if mission_spec.risk_level.value in ("R3", "R4") else 1

        # ── 4. Context deduplication ──
        all_context_items = self._flatten_context(context)
        deduplicated_items, removed_count = self._deduplicate_context(
            all_context_items
        )

        # ── 5. Build system prompt ──
        system_parts: list[str] = [
            "NEXARA PRIME Adaptive Runtime Worker.",
            "Follow the WorkContract. Use only mounted capabilities.",
            "Emit evidence for every action. Stop on policy conflict.",
            f"Disclosure level: {initial_disclosure} - {disclosure_system[initial_disclosure]}",
        ]

        if evidence_refs:
            system_parts.append(
                f"Evidence references ({len(evidence_refs)}): {', '.join(evidence_refs[:10])}"
                + (f" and {len(evidence_refs) - 10} more" if len(evidence_refs) > 10 else "")
            )
        if skill_refs:
            system_parts.append(
                f"Skill references ({len(skill_refs)}): {', '.join(skill_refs[:5])}"
                + (f" and {len(skill_refs) - 5} more" if len(skill_refs) > 5 else "")
            )

        # Security: never strip security constraints, permissions, or tool scopes
        system_parts.append(
            f"Security constraints: risk_level={mission_spec.risk_level.value if hasattr(mission_spec.risk_level, 'value') else mission_spec.risk_level}"
        )
        system_parts.append(
            f"Permissions & tool scopes: {', '.join(capabilities[:15])}"
            + (f" and {len(capabilities) - 15} more" if len(capabilities) > 15 else "")
        )

        system_text = "\n".join(system_parts)

        # ── 6. Build task prompt ──
        task_parts: list[str] = []
        task_parts.append(f"Mission: {mission_spec.objective}")
        task_parts.append(
            f"Roles in this mission: {', '.join(roles)}"
        )
        task_parts.append("")
        task_parts.append("=== Role-Specific Context ===")
        for role, slice_text in role_specific_slices.items():
            task_parts.append(f"[{role}]\n{slice_text}")
            task_parts.append("")

        # Add deduplicated context items
        if deduplicated_items:
            task_parts.append("=== Context ===")
            task_parts.extend(deduplicated_items[:20])

        # Object references (compact form)
        obj_refs_str: list[str] = []
        for key, value in context.items():
            ref_key = self._make_reference_key(key, value)
            obj_refs_str.append(ref_key)

        task_text = "\n".join(task_parts)

        # ── 7. Token estimation (≈4 chars per token) ──
        raw_context_chars = len(str(context)) + len(str(mission_spec))
        compiled_chars = len(system_text) + len(task_text)
        raw_context_tokens = max(1, raw_context_chars // 4)
        compiled_tokens = max(1, compiled_chars // 4)

        token_savings = raw_context_tokens - compiled_tokens
        token_savings_ratio = (
            token_savings / raw_context_tokens if raw_context_tokens > 0 else 0.0
        )

        # Context items tracked
        context_items_removed = removed_count
        context_items_referenced = len(evidence_refs) + len(skill_refs) + len(obj_refs_str)

        # ── 8. Build record ──
        record = TokenCompilationRecord(
            record_id=new_id("tcompile"),
            mission_id=mission_spec.mission_id,
            raw_context_tokens=raw_context_tokens,
            compiled_context_tokens=compiled_tokens,
            token_savings_ratio=token_savings_ratio,
            context_items_removed=context_items_removed,
            context_items_referenced=context_items_referenced,
            shared_immutable_context=shared_immutable,
            role_slices=list(role_specific_slices.keys()),
        )

        # ── 9. Build compiled prompt ──
        prompt = CompiledPrompt(
            prompt_id=new_id("prompt"),
            mission_id=mission_spec.mission_id,
            system=system_text,
            task=task_text,
            skill_refs=skill_refs,
            object_refs=obj_refs_str,
            evidence_refs=evidence_refs,
            estimated_tokens=compiled_tokens,
        )

        # Cache the summary for progressive disclosure
        self._summary_cache[mission_spec.mission_id] = self._build_summary(
            shared_immutable, role_specific_slices, obj_refs_str
        )
        self._disclosure_levels[mission_spec.mission_id] = initial_disclosure

        return prompt, record

    # ── Summary Cache ───────────────────────────────────────────────

    def _build_summary(
        self,
        shared_immutable: dict[str, Any],
        role_slices: dict[str, str],
        object_refs: list[str],
    ) -> str:
        """Build a compact summary for caching."""
        lines: list[str] = [
            f"Mission: {shared_immutable.get('objective', '')[:200]}",
            f"Roles: {', '.join(role_slices.keys())}",
            f"Object refs: {len(object_refs)}",
        ]
        return "\n".join(lines)

    def get_summary(self, mission_id: str) -> str | None:
        """Retrieve the cached summary for a mission."""
        return self._summary_cache.get(mission_id)

    def get_disclosure_level(self, mission_id: str) -> int:
        """Get the current disclosure level for a mission."""
        return self._disclosure_levels.get(mission_id, 1)

    def increase_disclosure(self, mission_id: str) -> int:
        """Increase the disclosure level (up to 3) for a mission."""
        current = self._disclosure_levels.get(mission_id, 1)
        new_level = min(current + 1, 3)
        self._disclosure_levels[mission_id] = new_level
        return new_level

    def clear_cache(self, mission_id: str | None = None) -> None:
        """Clear the summary cache for one or all missions."""
        if mission_id:
            self._summary_cache.pop(mission_id, None)
            self._disclosure_levels.pop(mission_id, None)
        else:
            self._summary_cache.clear()
            self._disclosure_levels.clear()

    # ── Internal ────────────────────────────────────────────────────

    @staticmethod
    def _flatten_context(context: dict[str, Any]) -> list[str]:
        """Flatten a nested context dict into a list of text items."""
        items: list[str] = []

        def _walk(prefix: str, value: Any) -> None:
            if isinstance(value, dict):
                for k, v in value.items():
                    _walk(f"{prefix}.{k}" if prefix else k, v)
            elif isinstance(value, list):
                if all(isinstance(i, str) for i in value):
                    items.append(f"{prefix}: {'; '.join(value)}")
                else:
                    for i, v in enumerate(value):
                        _walk(f"{prefix}[{i}]", v)
            else:
                items.append(f"{prefix}: {value}")

        _walk("", context)
        return items

    @staticmethod
    def _deduplicate_context(items: list[str]) -> tuple[list[str], int]:
        """Remove duplicates from context items.

        Returns (deduplicated_items, removed_count).
        """
        seen: set[str] = set()
        deduped: list[str] = []
        for item in items:
            # Create a normalized key for dedup
            norm = item.strip().lower()
            if norm not in seen:
                seen.add(norm)
                deduped.append(item)
        removed = len(items) - len(deduped)
        return deduped, removed

    @staticmethod
    def _make_reference_key(key: str, value: Any) -> str:
        """Create a short reference key for an object."""
        value_str = str(value)
        if len(value_str) > 40:
            # Create a content-addressed hash reference
            content_hash = hashlib.sha256(
                value_str.encode("utf-8")
            ).hexdigest()[:8]
            return f"ref:{key}[{content_hash}]"
        return f"ref:{key}"
