"""
NEXARA Dynamic Prompt Builder V1

Generates PromptPackage with deterministic hashing.
Provider-specific adapters wrap the package without altering governance semantics.

NSEC V2.1 §5.D
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field

from .models import now_iso


@dataclass(frozen=True)
class PromptPackage:
    """Deterministically-constructed prompt with reproducible hash."""

    prompt_package_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    mission_id: str = ""
    model_route_id: str = ""
    model: str = ""
    provider: str = ""
    # content sections
    system_anchors: str = ""
    governance_constraints: str = ""
    mission_contract: str = ""
    selected_memories: str = ""
    evidence_references: str = ""
    tool_policy: str = ""
    output_schema: str = ""
    # metadata
    token_allocation: int = 100_000
    retry_number: int = 0
    parent_prompt_package: str = ""
    sha256: str = ""
    created_at: str = field(default_factory=now_iso)

    def __post_init__(self):
        if not self.sha256:
            canonical = self._canonical_form()
            object.__setattr__(self, "sha256", hashlib.sha256(canonical.encode()).hexdigest())

    def _canonical_form(self) -> str:
        """Deterministic ordering for reproducible hashing."""
        return json.dumps({
            "mission_id": self.mission_id,
            "system_anchors": self.system_anchors,
            "governance_constraints": self.governance_constraints,
            "mission_contract": self.mission_contract,
            "selected_memories": self.selected_memories,
            "evidence_references": self.evidence_references,
            "tool_policy": self.tool_policy,
            "output_schema": self.output_schema,
            "retry_number": self.retry_number,
            "parent_prompt_package": self.parent_prompt_package,
        }, sort_keys=True, ensure_ascii=False)


class DynamicPromptBuilder:
    """
    Builds PromptPackage from KnowledgeAnchor + Mission Contract + Model Route.

    Deterministic: fixed ordering, fixed serialization, reproducible hash.
    Never leaks secrets. Never allows model to rewrite Soul.
    """

    def build(
        self,
        mission_id: str,
        anchors: str,
        governance: str,
        contract: str,
        memories: str,
        evidence: str,
        tool_policy: str,
        output_schema: str,
        model_name: str = "",
        provider: str = "",
        route_id: str = "",
        retry: int = 0,
        parent_package: str = "",
        token_budget: int = 100_000,
    ) -> PromptPackage:
        return PromptPackage(
            mission_id=mission_id,
            model_route_id=route_id,
            model=model_name,
            provider=provider,
            system_anchors=anchors,
            governance_constraints=governance,
            mission_contract=contract,
            selected_memories=memories,
            evidence_references=evidence,
            tool_policy=tool_policy,
            output_schema=output_schema,
            token_allocation=token_budget,
            retry_number=retry,
            parent_prompt_package=parent_package,
        )

    def to_provider_format(self, package: PromptPackage, provider: str) -> dict:
        """Provider-specific adapter. Must not change governance semantics."""
        base = {
            "role": "system",
            "content": (
                f"{package.system_anchors}\n\n"
                f"{package.governance_constraints}\n\n"
                f"{package.mission_contract}\n\n"
                f"{package.tool_policy}"
            ),
        }
        # Provider-specific wrappers (preserve governance semantics)
        if provider == "openai":
            return {"messages": [base]}
        return {"system": base["content"]}
