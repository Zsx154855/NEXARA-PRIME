"""Policy engine — evaluates policy rules for permission and execution decisions."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .command_classifier import RiskLevel


class PolicyDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    ASK_HUMAN = "ask_human"


@dataclass
class PolicyRule:
    name: str
    action_pattern: str
    risk_level: RiskLevel
    decision: PolicyDecision
    reversible: bool = True
    require_evidence: bool = False
    description: str = ""


class PolicyEngine:
    """Evaluates policies against commands and risk levels."""

    def __init__(self) -> None:
        self._rules: list[PolicyRule] = []
        self._register_defaults()

    def _register_defaults(self) -> None:
        defaults = [
            PolicyRule("read_only", "^Read$|^Glob$|^Grep$|^LSP$|^Bash$.*ls|find|grep",
                       RiskLevel.R0, PolicyDecision.ALLOW, True,
                       description="Pure read operations — always allowed"),
            PolicyRule("git_safe", "git (status|diff|log|branch|rev-parse|ls-remote|stash list)",
                       RiskLevel.R0, PolicyDecision.ALLOW, True,
                       description="Read-only git operations"),
            PolicyRule("test_run", "pytest|ruff check|mypy|tsc|swift test",
                       RiskLevel.R1, PolicyDecision.ALLOW, True,
                       description="Test and lint execution"),
            PolicyRule("build_run", "swift build|npm run build|pip install -e",
                       RiskLevel.R1, PolicyDecision.ALLOW, True,
                       description="Local build execution"),
            PolicyRule("write_files", "Write|Edit|mkdir|touch|cp|mv",
                       RiskLevel.R2, PolicyDecision.ALLOW, True,
                       description="File modifications — reversible"),
            PolicyRule("git_worktree", "git (worktree|checkout|switch|stash|branch -c)",
                       RiskLevel.R2, PolicyDecision.ALLOW, True,
                       description="Git branch and worktree — reversible"),
            PolicyRule("git_push_work", "git push origin work/",
                       RiskLevel.R3, PolicyDecision.ALLOW, True,
                       description="Push to work branches — allowed"),
            PolicyRule("gh_pr_read", "gh pr (view|list|checks|diff|status)",
                       RiskLevel.R0, PolicyDecision.ALLOW, True,
                       description="Read-only GitHub PR operations"),
            PolicyRule("no_force_push", "git push.*(--force|--delete)",
                       RiskLevel.R4, PolicyDecision.DENY, False,
                       description="Force push — denied"),
            PolicyRule("no_main_merge", "gh pr merge",
                       RiskLevel.R4, PolicyDecision.ASK_HUMAN, False,
                       description="PR merge — requires human"),
            PolicyRule("no_sudo", "sudo",
                       RiskLevel.R4, PolicyDecision.DENY, False,
                       description="sudo — denied"),
        ]
        for rule in defaults:
            self.add_rule(rule)

    def add_rule(self, rule: PolicyRule) -> None:
        self._rules.append(rule)

    def evaluate(self, command: str, risk_level: RiskLevel) -> PolicyDecision:
        import re
        for rule in self._rules:
            if re.search(rule.action_pattern, command, re.IGNORECASE):
                if rule.risk_level == risk_level or rule.risk_level.value >= risk_level.value:
                    return rule.decision
        # Defaults based on risk level
        if risk_level in (RiskLevel.R0, RiskLevel.R1):
            return PolicyDecision.ALLOW
        if risk_level == RiskLevel.R2:
            return PolicyDecision.ALLOW
        if risk_level == RiskLevel.R3:
            return PolicyDecision.ASK_HUMAN
        return PolicyDecision.DENY
