"""NEXARA Council V2 — Token Governor

Manages token budgets across council agents, enforces token limits,
optimizes context windows, and tracks costs.

Token modes:
- AGGRESSIVE: Maximum savings, aggressive compression
- BALANCED: Trade quality for cost at thresholds
- QUALITY: Token limits are advisory only
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TokenMode(str, Enum):
    AGGRESSIVE = "AGGRESSIVE"
    BALANCED = "BALANCED"
    QUALITY = "QUALITY"


@dataclass
class TokenBudget:
    """Per-agent token budget."""
    agent_id: str
    max_input_tokens: int = 8000
    max_output_tokens: int = 4096
    tokens_used_input: int = 0
    tokens_used_output: int = 0
    summary_threshold: float = 0.4  # Summarize when 40% of budget used
    mode: TokenMode = TokenMode.AGGRESSIVE


@dataclass
class TokenUsage:
    """Tracked token usage for a mission."""
    mission_id: str
    agent_budgets: dict[str, TokenBudget] = field(default_factory=dict)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    compression_count: int = 0
    started_at: float = field(default_factory=time.time)


class TokenGovernor:
    """Governs token usage across the council.

    AGGRESSIVE mode rules:
    - 禁止重复解释 (No repeated explanations)
    - 禁止重复读取无关文件 (No re-reading irrelevant files)
    - 优先摘要上下文 (Prefer contextual summaries)
    - 优先增量分析 (Prefer incremental analysis)
    - 大任务拆 Evidence Chunk (Split large tasks into evidence chunks)
    - 每阶段生成状态快照 (Generate state snapshots per phase)
    """

    # Budget per agent seat
    _DEFAULT_BUDGETS: dict[str, int] = {
        "H-CHAIRMAN": 12000,   # Chairman needs full context
        "H-STAFF": 10000,      # Staff needs broad context
        "H-ARCH": 8000,        # Architect needs design context
        "H-CODE": 8000,        # Coder needs code context
        "H-EXEC": 4000,        # Executor needs minimal context
        "H-RED": 8000,         # Red team needs attack surface
        "H-JUDGE": 8000,       # Judge needs full evidence
        "H-MEM": 6000,         # Memory needs structured data
        "H-TOKEN": 4000,       # Token governor self-limits
    }

    # Maximum total tokens per mission
    _MISSION_MAX_TOKENS: dict[TokenMode, int] = {
        TokenMode.AGGRESSIVE: 50000,
        TokenMode.BALANCED: 100000,
        TokenMode.QUALITY: 200000,
    }

    @classmethod
    def create_budget(cls, agent_id: str, mode: TokenMode = TokenMode.AGGRESSIVE) -> TokenBudget:
        """Create a token budget for an agent."""
        max_input = cls._DEFAULT_BUDGETS.get(agent_id, 8000)
        return TokenBudget(
            agent_id=agent_id,
            max_input_tokens=max_input,
            mode=mode,
        )

    @classmethod
    def should_compress(cls, budget: TokenBudget) -> bool:
        """Check if budget has exceeded the compression threshold."""
        if budget.max_input_tokens == 0:
            return False
        usage_ratio = budget.tokens_used_input / budget.max_input_tokens
        return usage_ratio >= budget.summary_threshold

    @classmethod
    def enforce_budget(cls, usage: TokenUsage, mode: TokenMode = TokenMode.AGGRESSIVE) -> list[str]:
        """Enforce budget limits and return violations/warnings.

        Returns:
            List of violation messages (empty = all clear)
        """
        violations: list[str] = []

        # Mission-level cap
        mission_cap = cls._MISSION_MAX_TOKENS.get(mode, 50000)
        mission_total = usage.total_input_tokens + usage.total_output_tokens
        if mission_total > mission_cap:
            violations.append(
                f"MISSION_OVER_BUDGET: {mission_total}/{mission_cap} tokens used. "
                f"Required: compression or approval for budget increase."
            )

        # Per-agent caps
        for agent_id, budget in usage.agent_budgets.items():
            agent_total = budget.tokens_used_input + budget.tokens_used_output
            agent_cap = budget.max_input_tokens + budget.max_output_tokens
            if agent_total > agent_cap * 1.2:  # 20% grace
                violations.append(
                    f"AGENT_OVER_BUDGET: {agent_id} used {agent_total}/{agent_cap} tokens."
                )

        return violations

    @classmethod
    def optimize_routing(cls, agents: list[str], mode: TokenMode = TokenMode.AGGRESSIVE) -> list[str]:
        """Optimize agent selection to minimize token cost.

        For AGGRESSIVE mode, prefer agents with lower default budgets
        when quality requirements can still be met.
        """
        if mode != TokenMode.AGGRESSIVE:
            return agents

        # Sort by budget (ascending) — prefer cheaper agents
        sorted_agents = sorted(agents, key=lambda a: cls._DEFAULT_BUDGETS.get(a, 8000))

        # Always keep CHAIRMAN if present
        result = []
        if "H-CHAIRMAN" in sorted_agents:
            result.append("H-CHAIRMAN")
            sorted_agents.remove("H-CHAIRMAN")

        # Always keep RED and JUDGE for high-risk
        required_high_risk = {"H-RED", "H-JUDGE"}
        for r in required_high_risk:
            if r in sorted_agents:
                result.append(r)
                sorted_agents.remove(r)

        # Fill remaining from cheapest
        result.extend(sorted_agents[:5])  # Cap at 5 in aggressive mode

        return result

    @classmethod
    def generate_status_snapshot(cls, usage: TokenUsage) -> dict:
        """Generate a compact status snapshot for the current phase."""
        return {
            "mission_id": usage.mission_id,
            "total_tokens": usage.total_input_tokens + usage.total_output_tokens,
            "compression_count": usage.compression_count,
            "agent_breakdown": {
                aid: {
                    "input": b.tokens_used_input,
                    "output": b.tokens_used_output,
                    "at_threshold": cls.should_compress(b),
                }
                for aid, b in usage.agent_budgets.items()
            },
            "elapsed_seconds": time.time() - usage.started_at,
        }
