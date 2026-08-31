"""V1.2 Intelligence Layer — CapabilityRegistry.

Register Capability objects and match a goal objective to the best capability
by keyword overlap over name/description. Read-only over V1.1.
"""
from __future__ import annotations

import re
from typing import Any

from .contracts import Capability

__all__ = ["CapabilityRegistry"]


def _tokens(text: str) -> set[str]:
    """Normalized keyword tokens: latin words + CJK character bigrams.

    CJK is bigram-tokenized (no word segmentation available) so short capability
    descriptions match longer goal objectives by shared bigrams (e.g.
    "检查运行时健康" vs "检查运行状态" share 检查/查运/运行).
    """
    tokens = {t for t in re.findall(r"[a-zA-Z0-9]+", (text or "").lower())}
    for run in re.findall(r"[\u4e00-\u9fff]+", (text or "")):
        for i in range(len(run) - 1):
            tokens.add(run[i:i + 2])
    return tokens


class CapabilityRegistry:
    """Key/value store of capabilities with keyword-based matching."""

    def __init__(self):
        self._caps: dict[str, Capability] = {}

    def register(self, cap: Capability) -> Capability:
        self._caps[cap.id] = cap
        return cap

    def match(self, goal_objective: str) -> Capability | None:
        goal = goal_objective or ""
        goal_lower = goal.lower()
        # 1) exact/substring containment over name or description.
        for cap in self._caps.values():
            if goal and (goal_lower in cap.name.lower() or goal_lower in cap.description.lower()):
                return cap
        # 2) keyword-overlap fallback.
        goal_tokens = _tokens(goal)
        if not goal_tokens:
            return None
        best: tuple[int, Capability] | None = None
        for cap in self._caps.values():
            hay = _tokens(cap.name + " " + cap.description)
            overlap = len(goal_tokens & hay)
            if overlap and (best is None or overlap > best[0]):
                best = (overlap, cap)
        return best[1] if best else None

    def select_tools(self, cap: Capability) -> list[str]:
        return list(cap.tools)
