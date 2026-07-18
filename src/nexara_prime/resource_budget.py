from __future__ import annotations

from .models import AdaptiveMode, BudgetUsage, ResourceBudget, now_iso


class ResourceBudgetManager:
    """Manages resource budget creation, usage tracking, and over-budget
    enforcement for adaptive missions.

    Each mission gets a ResourceBudget tailored to its adaptive mode:
      - S0 (minimal):   token_budget=10K, cost_budget=0.5, wall_time=60s,  tools=10
      - S1 (standard):  token_budget=50K, cost_budget=2.0, wall_time=120s, tools=25
      - S2 (generous):  token_budget=150K, cost_budget=8.0, wall_time=300s, tools=50
      - S3 (maximum):   token_budget=500K, cost_budget=25.0, wall_time=600s, tools=150

    Over-budget actions escalate through a ladder:
        warn → degrade_model (switch to flash) → reduce_agents (halve count)
        → compress_context → request_human → stop
    """

    # ── Mode-to-budget mapping ───────────────────────────────────────────────

    _MODE_BUDGETS: dict[str, dict[str, int | float]] = {
        AdaptiveMode.S0.value: {
            "token_budget": 10_000,
            "cost_budget": 0.5,
            "wall_time_budget_ms": 60_000,
            "tool_call_budget": 10,
            "retry_budget": 2,
            "agent_count_budget": 1,
            "browser_budget": 3,
            "evidence_budget": 20,
        },
        AdaptiveMode.S1.value: {
            "token_budget": 50_000,
            "cost_budget": 2.0,
            "wall_time_budget_ms": 120_000,
            "tool_call_budget": 25,
            "retry_budget": 4,
            "agent_count_budget": 4,
            "browser_budget": 6,
            "evidence_budget": 50,
        },
        AdaptiveMode.S2.value: {
            "token_budget": 150_000,
            "cost_budget": 8.0,
            "wall_time_budget_ms": 300_000,
            "tool_call_budget": 50,
            "retry_budget": 6,
            "agent_count_budget": 8,
            "browser_budget": 10,
            "evidence_budget": 100,
        },
        AdaptiveMode.S3.value: {
            "token_budget": 500_000,
            "cost_budget": 25.0,
            "wall_time_budget_ms": 600_000,
            "tool_call_budget": 150,
            "retry_budget": 10,
            "agent_count_budget": 16,
            "browser_budget": 20,
            "evidence_budget": 250,
        },
    }

    # ── Over-budget threshold and action ladder ──────────────────────────────

    # (threshold fraction of budget, action)
    _OVER_BUDGET_LADDER: list[tuple[float, str]] = [
        (0.80, "warn"),
        (0.95, "degrade_model"),
        (1.00, "reduce_agents"),
        (1.10, "compress_context"),
        (1.25, "request_human"),
        (1.50, "stop"),
    ]

    # ── Create ───────────────────────────────────────────────────────────────

    def create_budget(
        self,
        mission_id: str,
        adaptive_mode: AdaptiveMode | str,
        token_budget: int | None = None,
        cost_budget: float | None = None,
        wall_time_budget_ms: int | None = None,
        tool_call_budget: int | None = None,
        retry_budget: int | None = None,
        agent_count_budget: int | None = None,
        browser_budget: int | None = None,
        evidence_budget: int | None = None,
    ) -> ResourceBudget:
        """Create a ResourceBudget for the given mission.

        Defaults are drawn from the mode-to-budget mapping.  Any explicit
        keyword argument overrides the mode default.
        """
        defaults = self._MODE_BUDGETS.get(
            adaptive_mode.value if hasattr(adaptive_mode, 'value') else adaptive_mode,
            self._MODE_BUDGETS[AdaptiveMode.S0.value],
        )

        budget = ResourceBudget(
            mission_id=mission_id,
            token_budget=token_budget if token_budget is not None else defaults["token_budget"],  # type: ignore[assignment]
            cost_budget=cost_budget if cost_budget is not None else defaults["cost_budget"],  # type: ignore[assignment]
            wall_time_budget_ms=wall_time_budget_ms if wall_time_budget_ms is not None else defaults["wall_time_budget_ms"],  # type: ignore[assignment]
            tool_call_budget=tool_call_budget if tool_call_budget is not None else defaults["tool_call_budget"],  # type: ignore[assignment]
            retry_budget=retry_budget if retry_budget is not None else defaults["retry_budget"],  # type: ignore[assignment]
            agent_count_budget=agent_count_budget if agent_count_budget is not None else defaults["agent_count_budget"],  # type: ignore[assignment]
            browser_budget=browser_budget if browser_budget is not None else defaults["browser_budget"],  # type: ignore[assignment]
            evidence_budget=evidence_budget if evidence_budget is not None else defaults["evidence_budget"],  # type: ignore[assignment]
            created_at=now_iso(),
        )
        return budget

    # ── Track usage ──────────────────────────────────────────────────────────

    def track_usage(
        self,
        mission_id: str,
        budget_id: str,
        category: str,
        amount: int | float,
        usage: BudgetUsage | None = None,
    ) -> BudgetUsage:
        """Record a resource consumption event against a BudgetUsage record.

        Parameters
        ----------
        mission_id : str
            Mission identifier.
        budget_id : str
            Budget identifier to associate usage with.
        category : str
            One of: ``tokens``, ``cost``, ``wall_time``, ``tool_calls``,
            ``retries``, ``agents``, ``browser_calls``, ``evidence``.
        amount : int | float
            Amount consumed.
        usage : BudgetUsage | None
            Existing usage record to update.  If None, a new one is created.

        Returns
        -------
        BudgetUsage with the (possibly new) accumulated usage.
        """
        if usage is None:
            usage = BudgetUsage(
                mission_id=mission_id,
                budget_id=budget_id,
                created_at=now_iso(),
            )

        cat = category.strip().lower()
        if cat == "tokens":
            usage.tokens_used += int(amount)
        elif cat == "cost":
            usage.cost_used += float(amount)
        elif cat == "wall_time":
            usage.wall_time_used_ms += int(amount)
        elif cat == "tool_calls":
            usage.tool_calls_used += int(amount)
        elif cat == "retries":
            usage.retries_used += int(amount)
        elif cat == "agents":
            usage.agents_spawned += int(amount)
        elif cat == "browser_calls":
            usage.browser_calls_used += int(amount)
        elif cat == "evidence":
            usage.evidence_used += int(amount)
        else:
            raise ValueError(f"Unknown budget category: {category!r}")

        usage.updated_at = now_iso()
        return usage

    # ── Check budget ─────────────────────────────────────────────────────────

    def check_budget(
        self,
        usage: BudgetUsage,
        budget: ResourceBudget,
    ) -> dict:
        """Compare usage against budget limits and return an enforcement action.

        Returns
        -------
        dict with keys:
          - ``within_budget`` (bool) — True when no limits are exceeded.
          - ``violations`` (list[str]) — human-readable violation descriptions.
          - ``action`` (str) — enforcement action: ``ok``, ``warn``,
            ``degrade_model``, ``reduce_agents``, ``compress_context``,
            ``request_human``, or ``stop``.
          - ``usage_pct`` (dict) — percentage used per category.
        """
        violations: list[str] = []
        usage_pct: dict[str, float] = {}

        # ── Per-category usage percentages ──────────────────────────────────
        checks = [
            ("tokens", usage.tokens_used, budget.token_budget),
            ("cost", usage.cost_used, budget.cost_budget),
            ("wall_time", usage.wall_time_used_ms, budget.wall_time_budget_ms),
            ("tool_calls", usage.tool_calls_used, budget.tool_call_budget),
            ("retries", usage.retries_used, budget.retry_budget),
            ("agents", usage.agents_spawned, budget.agent_count_budget),
            ("browser_calls", usage.browser_calls_used, budget.browser_budget),
            ("evidence", usage.evidence_used, budget.evidence_budget),
        ]

        max_pct = 0.0
        for name, used, limit in checks:
            pct = (used / limit * 100.0) if limit > 0 else 0.0
            usage_pct[name] = round(pct, 1)
            if pct > max_pct:
                max_pct = pct
            if used > limit:
                violations.append(
                    f"{name}: {used} used exceeds budget {limit} "
                    f"({pct:.1f}%)"
                )

        # ── Determine action ────────────────────────────────────────────────
        action = self._over_budget_action(max_pct / 100.0)

        return {
            "within_budget": len(violations) == 0,
            "violations": violations,
            "action": action,
            "usage_pct": usage_pct,
        }

    # ── Public helpers ───────────────────────────────────────────────────────

    def get_defaults_for_mode(self, mode: AdaptiveMode) -> dict[str, int | float]:
        """Return the default budget values for a given adaptive mode."""
        return dict(self._MODE_BUDGETS.get(mode.value, self._MODE_BUDGETS[AdaptiveMode.S0.value]))

    def has_budget_remaining(self, usage: BudgetUsage, budget: ResourceBudget) -> bool:
        """Quick check: is there still room in every budget category?"""
        checks = [
            (usage.tokens_used, budget.token_budget),
            (usage.cost_used, budget.cost_budget),
            (usage.wall_time_used_ms, budget.wall_time_budget_ms),
            (usage.tool_calls_used, budget.tool_call_budget),
        ]
        return all(used <= limit for used, limit in checks)

    # ── Internal helpers ─────────────────────────────────────────────────────

    @classmethod
    def _over_budget_action(cls, max_pct: float) -> str:
        """Walk the escalation ladder to find the right action for a given
        maximum usage fraction."""
        action = "ok"
        for threshold, act in cls._OVER_BUDGET_LADDER:
            if max_pct >= threshold:
                action = act
        return action
