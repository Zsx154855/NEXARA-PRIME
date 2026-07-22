"""Branch protection adapter for sovereign CI authority bridge.

Reads and modifies GitHub branch protection and rulesets via gh CLI.
Always snapshots before modifying. Never deletes existing non-status rules.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from typing import Any


SOVEREIGN_CONTEXT = "nexara/sovereign-delivery"


@dataclass
class ProtectionSnapshot:
    """Snapshot of branch protection state before modification."""

    branch: str
    mode: str  # "classic", "ruleset", "none"
    ruleset_id: int | None = None
    ruleset_json: dict[str, Any] | None = None
    required_checks_before: list[str] = field(default_factory=list)
    sha256: str = ""


class ProtectionAdapter:
    """Reads and modifies GitHub branch protection and rulesets."""

    def __init__(self, repo: str = "Zsx154855/NEXARA-PRIME") -> None:
        self.repo = repo

    def snapshot(self, branch: str = "main") -> ProtectionSnapshot:
        """Capture current branch protection state."""
        import hashlib

        # Check for classic protection
        classic = self._get_classic_protection(branch)
        if classic is not None:
            checks = classic.get("required_status_checks", {})
            contexts = checks.get("contexts", []) if isinstance(checks, dict) else []
            raw = json.dumps(classic, ensure_ascii=False, sort_keys=True)
            return ProtectionSnapshot(
                branch=branch, mode="classic",
                required_checks_before=contexts,
                sha256=hashlib.sha256(raw.encode()).hexdigest(),
            )

        # Check for ruleset
        ruleset = self._get_ruleset_for_branch(branch)
        if ruleset is not None:
            raw = json.dumps(ruleset, ensure_ascii=False, sort_keys=True)
            return ProtectionSnapshot(
                branch=branch, mode="ruleset",
                ruleset_id=ruleset.get("id"),
                ruleset_json=ruleset,
                required_checks_before=self._extract_required_checks(ruleset),
                sha256=hashlib.sha256(raw.encode()).hexdigest(),
            )

        return ProtectionSnapshot(branch=branch, mode="none")

    def set_required_check(self, branch: str = "main", context: str = SOVEREIGN_CONTEXT) -> bool:
        """Set the sovereign context as the only required status check."""
        snap = self.snapshot(branch)

        if snap.mode == "ruleset" and snap.ruleset_id and snap.ruleset_json:
            return self._update_ruleset_checks(snap.ruleset_id, snap.ruleset_json, [context])

        # Classic or none: use direct branch protection API
        return self._set_classic_required_check(branch, [context])

    def restore(self, snapshot: ProtectionSnapshot) -> bool:
        """Restore branch protection to snapshot state."""
        if snapshot.mode == "classic":
            return self._set_classic_required_check(
                snapshot.branch, snapshot.required_checks_before,
            )
        elif snapshot.mode == "ruleset" and snapshot.ruleset_id and snapshot.ruleset_json:
            return self._update_ruleset_checks(
                snapshot.ruleset_id, snapshot.ruleset_json,
                snapshot.required_checks_before,
            )
        return True  # nothing to restore

    # ── Private helpers ──

    def _get_classic_protection(self, branch: str) -> dict[str, Any] | None:
        try:
            r = subprocess.run(
                ["gh", "api", f"/repos/{self.repo}/branches/{branch}/protection"],
                capture_output=True, text=True, timeout=10,
            )
            if r.returncode == 0:
                return json.loads(r.stdout)
        except Exception:
            pass
        return None

    def _get_ruleset_for_branch(self, branch: str) -> dict[str, Any] | None:
        try:
            r = subprocess.run(
                ["gh", "api", f"/repos/{self.repo}/rulesets"],
                capture_output=True, text=True, timeout=10,
            )
            if r.returncode != 0:
                return None
            rulesets = json.loads(r.stdout)
            for rs in rulesets:
                conditions = rs.get("conditions", {})
                ref_name = conditions.get("ref_name", {})
                includes = ref_name.get("include", [])
                if f"refs/heads/{branch}" in includes:
                    # Fetch full ruleset
                    r2 = subprocess.run(
                        ["gh", "api", f"/repos/{self.repo}/rulesets/{rs['id']}"],
                        capture_output=True, text=True, timeout=10,
                    )
                    if r2.returncode == 0:
                        return json.loads(r2.stdout)
        except Exception:
            pass
        return None

    def _extract_required_checks(self, ruleset: dict[str, Any]) -> list[str]:
        """Extract required status check contexts from a ruleset."""
        checks: list[str] = []
        for rule in ruleset.get("rules", []):
            if rule.get("type") == "required_status_checks":
                params = rule.get("parameters", {})
                contexts = params.get("required_status_checks", [])
                if isinstance(contexts, list):
                    for c in contexts:
                        if isinstance(c, dict):
                            checks.append(c.get("context", ""))
                        else:
                            checks.append(str(c))
        return [c for c in checks if c]

    def _set_classic_required_check(self, branch: str, contexts: list[str]) -> bool:
        """Set required status checks via classic branch protection API."""
        try:
            payload = {
                "required_status_checks": {
                    "strict": True,
                    "contexts": contexts,
                },
            }
            r = subprocess.run(
                [
                    "gh", "api",
                    f"/repos/{self.repo}/branches/{branch}/protection/required_status_checks",
                    "--method", "PATCH",
                    "--input", "-",
                ],
                input=json.dumps(payload, ensure_ascii=False),
                capture_output=True, text=True, timeout=15,
            )
            return r.returncode == 0
        except Exception:
            return False

    def _update_ruleset_checks(self, ruleset_id: int, original: dict[str, Any], contexts: list[str]) -> bool:
        """Update a ruleset to only require the specified status checks."""
        try:
            # Build updated rules: preserve all non-status rules, replace status check contexts
            updated_rules = []
            for rule in original.get("rules", []):
                if rule.get("type") == "required_status_checks":
                    new_rule = dict(rule)
                    new_rule["parameters"] = dict(rule.get("parameters", {}))
                    new_rule["parameters"]["required_status_checks"] = [
                        {"context": c} for c in contexts
                    ]
                    updated_rules.append(new_rule)
                else:
                    updated_rules.append(rule)

            # If no required_status_checks rule exists, add it
            if not any(r.get("type") == "required_status_checks" for r in updated_rules):
                updated_rules.append({
                    "type": "required_status_checks",
                    "parameters": {
                        "required_status_checks": [{"context": c} for c in contexts],
                    },
                })

            payload = {
                "name": original.get("name", "main-protection"),
                "target": original.get("target", "branch"),
                "enforcement": original.get("enforcement", "active"),
                "conditions": original.get("conditions", {}),
                "rules": updated_rules,
            }

            r = subprocess.run(
                [
                    "gh", "api",
                    f"/repos/{self.repo}/rulesets/{ruleset_id}",
                    "--method", "PUT",
                    "--input", "-",
                ],
                input=json.dumps(payload, ensure_ascii=False),
                capture_output=True, text=True, timeout=15,
            )
            return r.returncode == 0
        except Exception:
            return False
