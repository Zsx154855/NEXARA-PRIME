"""Command risk classification — maps shell/tool invocations to risk levels (R0-R4).

Uses shell tokenisation, control-operator detection, redirection detection,
and mutating-option detection to prevent prefix-only matching from
auto-approving dangerous commands.
"""
from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from enum import Enum
from typing import ClassVar


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


# ── Shell structure detection (tokens, control operators, redirections) ──

# Shell control operators that allow multi-command execution
# | (pipe) is included — it spawns a second process with its own side effects
_CONTROL_OPERATORS: re.Pattern[str] = re.compile(
    r"(?<!\\)(?:&&|\|\||\||;|&|\\\n|\n)"
)

# Redirections that create/overwrite files
_REDIRECTION_PATTERN: re.Pattern[str] = re.compile(
    r"\d*>>?\s*\S|\d*>\s*\S|\d*&>\s*\S|\d*>>\s*\S"
)

# Mutating options on nominally-read-only commands
_MUTATING_OPTIONS: dict[str, list[str]] = {
    "find": ["-delete", "-exec", "-execdir", "-ok", "-okdir"],
    "git": ["push", "merge", "rebase", "tag", "add", "commit", "stash", "clean"],
}


def _has_control_operators(command: str) -> bool:
    """True if the command contains shell control operators (;, &&, ||, &, \\n)."""
    return bool(_CONTROL_OPERATORS.search(command))


def _has_redirection(command: str) -> bool:
    """True if the command contains output redirection (> , >>, &>, 2>)."""
    return bool(_REDIRECTION_PATTERN.search(command))


def _has_mutating_option(command: str, base_cmd: str) -> bool:
    """True if *base_cmd* is used with a known mutating option."""
    options = _MUTATING_OPTIONS.get(base_cmd, [])
    for opt in options:
        if opt in command:
            return True
    return False


# ── Interpreter snippet detection ──

# Any python -c or python - <<EOF invocation
_INTERPRETER_SNIPPET: re.Pattern[str] = re.compile(
    r"(?:python|python3|ruby|perl|node)\s+(?:-c\b|-\s*<<)"
)

# Dangerous Python/stdlib operations detectable via string match
_PYTHON_DANGEROUS_PATTERNS: list[str] = [
    r"\bopen\s*\(", r"\.write\s*\(", r"\.writelines\s*\(",
    r"\bsocket\b", r"\bsubprocess\b", r"\bos\.system\b",
    r"\bos\.remove\b", r"\bos\.unlink\b", r"\bos\.rmdir\b",
    r"\bshutil\.(?:rmtree|copytree|move|copy)\b",
    r"\bpathlib\.Path.*\.(?:unlink|rmdir|write_text|write_bytes)\b",
    r"\brequests?\b", r"\burllib\b", r"\bhttp\.client\b",
    r"\bexec\s*\(", r"\beval\s*\(", r"\bcompile\s*\(",
    r"\bimportlib\b", r"\b__import__\b",
    r"\bopenai\b", r"\banthropic\b",
    r"\bhashlib\b", r"\bcryptography\b",
    r"\bos\.(?:chmod|chown|mkdir|makedirs|rename|symlink|link)\b",
    r"\bkeyring\b", r"\bkeychain\b",
    r"\bprintenv\b", r"\bos\.environ\b", r"\bos\.getenv\b",
    r"\bdelete\b", r"\bdestroy\b", r"\bpurge\b",
]


def _python_snippet_is_dangerous(command: str) -> bool:
    """Check if a python -c / heredoc snippet contains dangerous operations."""
    for pattern in _PYTHON_DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return True
    return False


# ── gh api detection ──

def _gh_api_has_mutating_params(command: str) -> bool:
    """True if gh api has field/method params that make it mutating.

    Detects both space-separated and equals-form flags:
    - -f body=hi, --field body=hi, --field=body=hi
    - -F body=hi, --raw-field key=val, --raw-field=key=val
    - -X POST, -XPOST, --method POST, --method=POST, --method=DELETE
    """
    # Space-separated: -f value, --field value, -F value, --raw-field value
    if re.search(r"(?:-f|--field|--raw-field)\s", command):
        return True
    if re.search(r"(?:-F)\s", command):
        return True
    # Equals-form: --field=value, --raw-field=value
    if re.search(r"(?:--field|--raw-field)=", command):
        return True
    # -X method (space or glued): -X POST, -XPOST, -XDELETE
    if re.search(r"-X\s*(?:POST|PUT|PATCH|DELETE)", command, re.IGNORECASE):
        return True
    # --method with space or equals: --method POST, --method=POST, --method=DELETE
    if re.search(r"--method[\s=](?:POST|PUT|PATCH|DELETE)", command, re.IGNORECASE):
        return True
    return False


def _gh_api_has_non_get_method(command: str) -> bool:
    """Detect if gh api specifies a non-GET HTTP method.

    Handles: -X POST, -XPOST, --method POST, --method=POST, --method=DELETE, etc.
    """
    # -X (space or glued)
    m = re.search(r"-X\s*(\S+)", command, re.IGNORECASE)
    if m:
        method = m.group(1).upper()
        if method in ("POST", "PUT", "PATCH", "DELETE"):
            return True
    # --method (space or equals)
    m = re.search(r"--method[\s=](\S+)", command, re.IGNORECASE)
    if m:
        method = m.group(1).upper()
        if method in ("POST", "PUT", "PATCH", "DELETE"):
            return True
    return False


# ── git push refspec parsing ──

def _git_push_refspec_dangerous(command: str) -> bool:
    """Check if a git push command targets a non-work branch or uses force/delete."""
    # Block force push
    if re.search(r"(?:--force|--force-with-lease|--delete|\+)", command):
        return True
    # Detailed refspec parsing is done in PermissionBroker._validate_git_push_refspec
    return False


class CommandClassifier:
    """Maps command strings to risk levels via layered analysis.

    Layered analysis (executed in order):
    1. Shell structure scan — control operators, redirections, mutating options
    2. Interpreter snippet scan — python -c, heredocs
    3. gh api parameter scan — field/method detection
    4. Pattern-based classification (fallback)
    """

    # ── R4: Irreversible, sensitive, financial ──
    R4_PATTERNS: ClassVar[list[str]] = [
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
        r"chmod\s+[0-7]*7", r"chown\b",
    ]

    # ── R3: External or high-impact ──
    R3_PATTERNS: ClassVar[list[str]] = [
        r"git\s+push\b", r"git\s+merge\b",
        r"gh\s+pr\s+create", r"gh\s+pr\s+edit",
        r"curl\b", r"wget\b",
        r"npm\s+install\s+-g", r"pip\s+install\s+--global",
        r"brew\s+install", r"brew\s+uninstall",
        r"launchctl\s+load", r"launchctl\s+unload",
        r"codesign\b", r"notarytool\b",
    ]

    # ── R2: Reversible write ──
    R2_PATTERNS: ClassVar[list[str]] = [
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
    R1_PATTERNS: ClassVar[list[str]] = [
        r"python\s+-m\s+pytest\b", r"pytest\b",
        r"ruff\s+check\b", r"ruff\s+format\b",
        r"mypy\b", r"pyright\b",
        r"npx\s+tsc\b", r"npm\s+run\s+build\b",
        r"npm\s+ci\b", r"npm\s+test\b",
        r"swift\s+test\b",
        r"python\s+\S+\.py\b",
        r"node\s+\S+\.js\b",
    ]

    # ── R0: Pure read (validated) ──
    R0_PATTERNS: ClassVar[list[str]] = [
        r"^ls\b", r"^cat\b", r"^head\b", r"^tail\b",
        r"^find\b", r"^grep\b", r"^rg\b",
        r"^wc\b", r"^du\b", r"^df\b",
        r"^which\b", r"^where\b", r"^type\b",
        r"^echo\b", r"^pwd\b", r"^date\b",
        r"^uname\b", r"^hostname\b",
        r"^git\s+status\b", r"^git\s+log\b",
        r"^git\s+diff\b", r"^git\s+show\b",
        r"^git\s+rev-parse\b", r"^git\s+ls-\w",
        r"^gh\s+pr\s+view\b", r"^gh\s+pr\s+list\b",
        r"^gh\s+pr\s+checks\b", r"^gh\s+pr\s+diff\b",
        r"^gh\s+run\s+list\b", r"^gh\s+run\s+view\b",
        r"^pip\s+list\b", r"^pip\s+show\b",
        r"^npm\s+view\b", r"^npm\s+list\b",
        r"^swift\s+--version\b",
        r"^Read\b", r"^Glob\b", r"^Grep\b",
        r"^LSP\b",
        r"^cargo\s+check\b", r"^cargo\s+clippy\b",
    ]

    def classify(self, command: str, **kwargs: str) -> CommandClassification:
        """Classify a command string into a risk level.

        Layered analysis:
        1. High-risk patterns (R4, R3, R2) — checked first
        2. Interpreter snippets (python -c, heredocs)
        3. gh api parameter scan
        4. Shell structure scan (applied to R0/R1 candidates only)
        5. R1/R0 pattern matching
        """

        # ── Layer 0: Tokenize for structure analysis ──
        try:
            tokens = shlex.split(command)
        except ValueError:
            tokens = command.split()
        base_cmd = tokens[0] if tokens else ""

        # ── Layer 1: Interpreter snippets (python -c, heredocs) ──
        if _INTERPRETER_SNIPPET.search(command):
            if _python_snippet_is_dangerous(command):
                return CommandClassification(
                    command=command, risk_level=RiskLevel.R4,
                    kind=CommandKind.SYSTEM, auto_approvable=False,
                    reversible=False,
                    reason="python -c with dangerous operations (file write, network, subprocess, os.system) — R4",
                )
            return CommandClassification(
                command=command, risk_level=RiskLevel.R2,
                kind=CommandKind.UNKNOWN, auto_approvable=False,
                reversible=False,
                reason="python -c / interpreter snippet — default R2, cannot prove read-only",
            )

        # ── Layer 2: gh api parameter scan ──
        if re.match(r"^gh\s+api\b", command):
            # Check shell side effects FIRST before any R0 classification
            if _has_control_operators(command):
                return CommandClassification(
                    command=command, risk_level=RiskLevel.R3,
                    kind=CommandKind.NETWORK, auto_approvable=False,
                    reversible=False,
                    reason="gh api with shell control operators (;, &&, ||, |) — fail-closed to R3",
                )
            if _has_redirection(command):
                return CommandClassification(
                    command=command, risk_level=RiskLevel.R3,
                    kind=CommandKind.NETWORK, auto_approvable=False,
                    reversible=False,
                    reason="gh api with output redirection — fail-closed to R3",
                )
            # Check for mutating API params
            if _gh_api_has_mutating_params(command) or _gh_api_has_non_get_method(command):
                return CommandClassification(
                    command=command, risk_level=RiskLevel.R3,
                    kind=CommandKind.NETWORK, auto_approvable=False,
                    reversible=False,
                    reason="gh api with field/method/write params — R3, external side effect",
                )
            # Explicitly GET with no mutating params AND no shell side effects → R0
            return CommandClassification(
                command=command, risk_level=RiskLevel.R0,
                kind=CommandKind.NETWORK, auto_approvable=True,
                reversible=True,
                reason="gh api GET with no mutating params — read-only",
            )

        # ── Layer 3: High-risk pattern matching (R4 → R3) ──
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

        # ── Layer 4: Shell structure scan (before R2/R1/R0) ──
        # Check for hidden side effects that would make any command dangerous.
        if _has_control_operators(command):
            return CommandClassification(
                command=command, risk_level=RiskLevel.R3,
                kind=CommandKind.UNKNOWN, auto_approvable=False,
                reversible=False,
                reason="shell control operators detected (;, &&, ||, &) — fail-closed to R3",
            )
        if _has_redirection(command):
            return CommandClassification(
                command=command, risk_level=RiskLevel.R3,
                kind=CommandKind.WRITE, auto_approvable=False,
                reversible=False,
                reason="output redirection detected (>, >>, &>) — fail-closed to R3",
            )
        if _has_mutating_option(command, base_cmd):
            return CommandClassification(
                command=command, risk_level=RiskLevel.R3,
                kind=CommandKind.WRITE, auto_approvable=False,
                reversible=False,
                reason=f"mutating option on '{base_cmd}' detected — fail-closed to R3",
            )

        # ── Layer 5: R2 pattern matching ──
        for pattern in self.R2_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return CommandClassification(
                    command=command, risk_level=RiskLevel.R2,
                    kind=self._infer_kind(command), auto_approvable=True,
                    reversible=True, reason=f"matches R2 pattern: {pattern}",
                )

        # ── Layer 6: R1/R0 pattern matching ──
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
        # Default: fail closed
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
