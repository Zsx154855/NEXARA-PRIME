"""Risk-based permission broker — auto-approves R0-R2, escalates R3-R4.

R3 whitelist entries are re-validated for shell metacharacters before
auto-approval to prevent prefix-only bypasses.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .command_classifier import (
    CommandClassifier,
    RiskLevel,
    _has_control_operators,
    _has_redirection,
    _has_command_substitution,
    _has_process_substitution,
)


@dataclass
class PermissionDecision:
    command: str
    risk_level: RiskLevel
    decision: str  # "auto_approved", "policy_approved", "escalated", "denied"
    reason: str
    decision_id: str = ""
    mission_id: str = ""
    worker_id: str = ""
    decided_at: str = ""
    evidence_ref: str = ""


class PermissionBroker:
    """Unified permission broker for all workers.

    R0-R1: auto-approved.
    R2: auto-approved if policy allows and reversible.
    R3: auto-approved only for whitelisted actions with validated refspecs.
    R4: always escalated to human.
    """

    # Only allow pushes to refs/heads/work/*
    _WORK_BRANCH_REFSRC: re.Pattern[str] = re.compile(
        r"^refs/heads/work/|^work/"
    )
    _WORK_BRANCH_REFDST: re.Pattern[str] = re.compile(
        r"^refs/heads/work/"
    )

    def __init__(self, classifier: CommandClassifier | None = None) -> None:
        self._classifier = classifier or CommandClassifier()
        self._decisions: list[PermissionDecision] = []
        # Whitelist entries are now structured: (prefix, validator_fn | None)
        self._r3_whitelist: list[tuple[str, Any]] = [
            ("gh pr create", None),
            ("gh pr edit", None),
            ("gh pr view", None),
            ("git push origin ", self._validate_git_push_refspec),
        ]

    def evaluate(
        self, command: str, *,
        mission_id: str = "", worker_id: str = "",
        working_directory: str = "",
    ) -> PermissionDecision:
        classification = self._classifier.classify(command)
        risk = classification.risk_level
        now = datetime.now(timezone.utc).isoformat()

        decision_id = hashlib.sha256(
            f"{command}:{mission_id}:{worker_id}:{now}".encode()
        ).hexdigest()[:16]

        if risk in (RiskLevel.R0, RiskLevel.R1):
            decision = PermissionDecision(
                command=command, risk_level=risk, decision="auto_approved",
                reason=f"{risk.value} — always auto-approved", decision_id=decision_id,
                mission_id=mission_id, worker_id=worker_id, decided_at=now,
            )
        elif risk == RiskLevel.R2:
            if classification.reversible:
                decision = PermissionDecision(
                    command=command, risk_level=risk, decision="auto_approved",
                    reason="R2 reversible — auto-approved", decision_id=decision_id,
                    mission_id=mission_id, worker_id=worker_id, decided_at=now,
                )
            else:
                decision = PermissionDecision(
                    command=command, risk_level=risk, decision="escalated",
                    reason="R2 non-reversible — requires policy check",
                    decision_id=decision_id, mission_id=mission_id,
                    worker_id=worker_id, decided_at=now,
                )
        elif risk == RiskLevel.R3:
            if self._is_r3_whitelisted(command):
                decision = PermissionDecision(
                    command=command, risk_level=risk, decision="auto_approved",
                    reason="R3 whitelisted action", decision_id=decision_id,
                    mission_id=mission_id, worker_id=worker_id, decided_at=now,
                )
            else:
                decision = PermissionDecision(
                    command=command, risk_level=risk, decision="escalated",
                    reason="R3 requires human approval", decision_id=decision_id,
                    mission_id=mission_id, worker_id=worker_id, decided_at=now,
                )
        else:  # R4
            decision = PermissionDecision(
                command=command, risk_level=risk, decision="escalated",
                reason="R4 always requires human approval", decision_id=decision_id,
                mission_id=mission_id, worker_id=worker_id, decided_at=now,
            )

        self._decisions.append(decision)
        return decision

    def _is_r3_whitelisted(self, command: str) -> bool:
        """Check if command is in the R3 whitelist, with mandatory shell re-validation.

        BEFORE approval, the whitelist re-validates for:
        - pipe (|)
        - semicolon (;)
        - && / ||
        - redirection (> , >>, &>)
        - command substitution ($(...) or backticks)
        - process substitution (<(...) or >(...))
        - multiple commands (via shlex split)
        - shell injection metacharacters

        A single match fails the whitelist check — fail-closed.
        """
        # ── Mandatory pre-whitelist shell re-validation ──
        if _has_control_operators(command):
            return False
        if _has_redirection(command):
            return False
        if _has_command_substitution(command):
            return False
        if _has_process_substitution(command):
            return False
        # Multiple commands via whitespace-separated tokens beyond the prefix
        if "|" in command or ";" in command:
            return False

        # ── Whitelist prefix matching ──
        for prefix, validator in self._r3_whitelist:
            if command.startswith(prefix):
                if validator is not None:
                    return validator(command[len(prefix):].strip())
                return True
        return False

    @classmethod
    def _validate_git_push_refspec(cls, refspec_part: str) -> bool:
        """Validate git push refspec so only work/* → work/* is allowed.

        Rejects:
        - work/foo:main
        - work/foo:refs/heads/main
        - HEAD:main
        - --force, --delete, --force-with-lease
        - +work/foo:anything (force push prefix)
        - multiple refspecs
        """
        # Block flags that appear in the refspec position
        blocked_flags = {"--force", "--force-with-lease", "--delete", "-f", "-d"}
        refspec_tokens = refspec_part.split()
        for token in refspec_tokens:
            if token in blocked_flags:
                return False
            if token.startswith("--"):
                return False

        # Only allow a single refspec
        non_flag_tokens = [t for t in refspec_tokens if not t.startswith("-")]
        if len(non_flag_tokens) > 1:
            return False
        if not non_flag_tokens:
            # push without refspec — default push, uses push.default config
            # Only allow if we can verify the upstream; fail closed
            return False

        refspec = non_flag_tokens[0]

        # Block force-push prefix
        if refspec.startswith("+"):
            return False

        # Parse src:dst
        if ":" in refspec:
            src, dst = refspec.split(":", 1)
        else:
            src = refspec
            dst = refspec  # implicit: push src to same-named dst

        # Source must be a work branch
        if not cls._WORK_BRANCH_REFSRC.match(src):
            return False

        # Destination must be refs/heads/work/*
        if not cls._WORK_BRANCH_REFDST.match(dst):
            return False

        return True

    @property
    def auto_approved_count(self) -> int:
        return sum(1 for d in self._decisions if d.decision == "auto_approved")

    @property
    def escalated_count(self) -> int:
        return sum(1 for d in self._decisions if d.decision == "escalated")

    def get_decision(self, decision_id: str) -> PermissionDecision | None:
        for d in self._decisions:
            if d.decision_id == decision_id:
                return d
        return None

    def to_evidence(self) -> dict[str, Any]:
        return {
            "total_decisions": len(self._decisions),
            "auto_approved": self.auto_approved_count,
            "escalated": self.escalated_count,
            "decisions": [
                {
                    "id": d.decision_id, "command": d.command[:80],
                    "risk": d.risk_level.value, "decision": d.decision,
                }
                for d in self._decisions[-20:]  # last 20
            ],
        }
