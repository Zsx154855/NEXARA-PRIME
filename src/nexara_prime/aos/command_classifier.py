"""Command risk classification — maps shell/tool invocations to risk levels (R0-R4)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class RiskLevel(str, Enum):
    R0 = "R0"  # pure read
    R1 = "R1"  # safe local execution
    R2 = "R2"  # reversible write
    R3 = "R3"  # external / high-impact
    R4 = "R4"  # irreversible / sensitive / financial


class CommandKind(str, Enum):
    READ = "read"
    WRITE = "write"
    NETWORK = "network"
    GIT = "git"
    BUILD = "build"
    PACKAGE = "package"
    SYSTEM = "system"
    SECRET = "secret"
    DEPLOY = "deploy"
    UNKNOWN = "unknown"


@dataclass
class CommandClassification:
    command: str
    risk_level: RiskLevel
    kind: CommandKind
    auto_approvable: bool
    reversible: bool
    reason: str
    args: list[str] = field(default_factory=list)
    working_directory: str = ""


class CommandClassifier:
    """Maps command strings to risk levels via pattern matching.

    Built from policy rules; extensible via registration.
    """

    # ── R4: Irreversible, sensitive, financial ──
    R4_PATTERNS: list[str] = [
        r"rm\s+-rf", r"sudo\b", r"diskutil\b", r"dd\s+if=",
        r"git\s+push.*--force", r"git\s+push.*--delete",
        r"aws\s+.*delete", r"gcloud\s+.*delete",
        r"gh\s+repo\s+delete", r"gh\s+pr\s+merge",
        r"security\s+delete-keychain", r"secrets\b",
        r"openssl\s+.*-pass", r"keychain\b",
        r"curl.*\.com.*secret", r"env\b",
        r"printenv\b", r"echo\s+\$",
        r"npm\s+publish", r"twine\s+upload",
        r"gh\s+release\s+create", r"git\s+tag",
    ]

    # ── R3: External or high-impact ──
    R3_PATTERNS: list[str] = [
        r"git\s+push\b", r"git\s+merge\b",
        r"gh\s+pr\s+create", r"gh\s+pr\s+edit",
        r"curl\b", r"wget\b",
        r"npm\s+install\s+-g", r"pip\s+install\s+--global",
        r"brew\s+install", r"brew\s+uninstall",
        r"launchctl\s+load", r"launchctl\s+unload",
        r"codesign\b", r"notarytool\b",
    ]

    # ── R2: Reversible write ──
    R2_PATTERNS: list[str] = [
        r"git\s+add\b", r"git\s+commit\b", r"git\s+checkout\b",
        r"git\s+switch\b", r"git\s+branch\b", r"git\s+stash\b",
        r"git\s+worktree\b", r"git\s+rebase\b",
        r"pip\s+install\b", r"npm\s+install\b",
        r"pip\s+uninstall\b", r"npm\s+uninstall\b",
        r"mkdir\b", r"touch\b",
        r"Write\b", r"Edit\b",
        r"cp\b", r"mv\b",
        r">\s*/", r">>\s*/",
        r"swift\s+build\b", r"xcodebuild\b",
        r"python\s+-m\s+pip\s+install",
    ]

    # ── R1: Safe local execution ──
    R1_PATTERNS: list[str] = [
        r"python\s+-m\s+pytest\b", r"pytest\b",
        r"ruff\s+check\b", r"ruff\s+format\b",
        r"mypy\b", r"pyright\b",
        r"npx\s+tsc\b", r"npm\s+run\s+build\b",
        r"npm\s+ci\b", r"npm\s+test\b",
        r"swift\s+test\b",
        r"python\s+\S+\.py\b",
        r"node\s+\S+\.js\b",
    ]

    # ── R0: Pure read ──
    R0_PATTERNS: list[str] = [
        r"^ls\b", r"^cat\b", r"^head\b", r"^tail\b",
        r"^find\b", r"^grep\b", r"^rg\b",
        r"^wc\b", r"^du\b", r"^df\b",
        r"^which\b", r"^where\b", r"^type\b",
        r"^echo\b", r"^pwd\b", r"^date\b",
        r"^uname\b", r"^hostname\b",
        r"^git\s+status\b", r"^git\s+log\b",
        r"^git\s+diff\b", r"^git\s+show\b",
        r"^git\s+rev-parse\b", r"^git\s+ls-\w",
        r"^git\s+branch\b",
        r"^gh\s+pr\s+view\b", r"^gh\s+pr\s+list\b",
        r"^gh\s+pr\s+checks\b", r"^gh\s+pr\s+diff\b",
        r"^gh\s+api\b", r"^gh\s+run\s+list\b",
        r"^gh\s+run\s+view\b",
        r"^python\s+-c\b",
        r"^pip\s+list\b", r"^pip\s+show\b",
        r"^npm\s+view\b", r"^npm\s+list\b",
        r"^swift\s+--version\b",
        r"^Read\b", r"^Glob\b", r"^Grep\b",
        r"^LSP\b",
        r"^cargo\s+check\b", r"^cargo\s+clippy\b",
    ]

    def classify(self, command: str, **kwargs: str) -> CommandClassification:
        """Classify a command string into a risk level."""
        for pattern in self.R4_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return CommandClassification(
                    command=command, risk_level=RiskLevel.R4,
                    kind=self._infer_kind(command), auto_approvable=False,
                    reversible=False, reason=f"matches R4 pattern: {pattern}",
                )
        for pattern in self.R3_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return CommandClassification(
                    command=command, risk_level=RiskLevel.R3,
                    kind=self._infer_kind(command), auto_approvable=False,
                    reversible=False, reason=f"matches R3 pattern: {pattern}",
                )
        for pattern in self.R2_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return CommandClassification(
                    command=command, risk_level=RiskLevel.R2,
                    kind=self._infer_kind(command), auto_approvable=True,
                    reversible=True, reason=f"matches R2 pattern: {pattern}",
                )
        for pattern in self.R1_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return CommandClassification(
                    command=command, risk_level=RiskLevel.R1,
                    kind=self._infer_kind(command), auto_approvable=True,
                    reversible=True, reason=f"matches R1 pattern: {pattern}",
                )
        for pattern in self.R0_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return CommandClassification(
                    command=command, risk_level=RiskLevel.R0,
                    kind=self._infer_kind(command), auto_approvable=True,
                    reversible=True, reason=f"matches R0 pattern: {pattern}",
                )
        return CommandClassification(
            command=command, risk_level=RiskLevel.R2,
            kind=CommandKind.UNKNOWN, auto_approvable=False,
            reversible=False, reason="no pattern match — default R2",
        )

    @staticmethod
    def _infer_kind(command: str) -> CommandKind:
        if re.search(r"^(ls|cat|head|tail|find|grep|rg|wc|Read|Glob|Grep|LSP)", command):
            return CommandKind.READ
        if re.search(r"git\b", command):
            return CommandKind.GIT
        if re.search(r"(swift build|xcodebuild|npm run build|tsc|pytest|ruff)", command):
            return CommandKind.BUILD
        if re.search(r"(npm install|pip install|brew)", command):
            return CommandKind.PACKAGE
        if re.search(r"(curl|wget|gh api)", command):
            return CommandKind.NETWORK
        if re.search(r"(sudo|launchctl|codesign)", command):
            return CommandKind.SYSTEM
        if re.search(r"(secret|keychain|env|printenv)", command):
            return CommandKind.SECRET
        if re.search(r"(deploy|release|publish)", command):
            return CommandKind.DEPLOY
        if re.search(r"(Write|Edit|mkdir|touch|cp|mv)", command):
            return CommandKind.WRITE
        return CommandKind.UNKNOWN
