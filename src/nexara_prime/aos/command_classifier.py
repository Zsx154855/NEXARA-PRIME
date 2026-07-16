"""Command risk classification — maps shell/tool invocations to risk levels (R0-R4).

Uses shell tokenisation, control-operator detection, redirection detection,
command substitution detection, secret expansion detection, destructive git
detection, sensitive path detection, and mutating-option detection to prevent
prefix-only matching from auto-approving dangerous commands.
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


# ── Shell structure detection (tokens, control operators, redirections, substitution) ──

# Shell control operators that allow multi-command execution
# | (pipe) is included — it spawns a second process with its own side effects
_CONTROL_OPERATORS: re.Pattern[str] = re.compile(
    r"(?<!\\)(?:&&|\|\||\||;|&|\\\n|\n)"
)

# Redirections that create/overwrite files
_REDIRECTION_PATTERN: re.Pattern[str] = re.compile(
    r"\d*>>?\s*\S|\d*>\s*\S|\d*&>\s*\S|\d*>>\s*\S"
)

# Shell command substitution: $(...) and backticks
_COMMAND_SUBSTITUTION: re.Pattern[str] = re.compile(
    r"\$\([^)]*\)|`[^`]+`"
)

# Shell process substitution: <(cmd) and >(cmd) — always dangerous
_PROCESS_SUBSTITUTION: re.Pattern[str] = re.compile(
    r"[<>]\s*\([^)]+\)"
)

# Unsafe write targets — touch/cp/mv to these paths is R3/R4.
# Thread 2 (Codex V12): Extended to cover .npmrc, .docker/config.json,
# .config/gh/hosts.yml, .netrc, .pypirc, .git-credentials.
_UNSAFE_WRITE_TARGETS: re.Pattern[str] = re.compile(
    r"(?:"
    r"~/.bashrc|~/.zshrc|~/.profile|~/.bash_profile|"
    r"~/.ssh/|~/.aws/|"
    r"~/.npmrc\b|"
    r"~/.docker/config\.json|"
    r"~/.config/gh/hosts\.yml|"
    r"~/.netrc\b|"
    r"~/.pypirc\b|"
    r"~/.git-credentials\b|"
    r"\$HOME/\.ssh/|\$HOME/\.aws/|"
    r"\$HOME/\.npmrc\b|"
    r"\$HOME/\.docker/config\.json|"
    r"\$\{HOME\}/\.ssh/|\$\{HOME\}/\.aws/|"
    r"\$\{HOME\}/\.npmrc\b|"
    r"\$\{HOME\}/\.docker/config\.json|"
    r"/root/\.ssh/|/root/\.aws/|"
    r"/root/\.npmrc\b|"
    r"/root/\.docker/config\.json|"
    r"/etc/|"
    r"/Library/|"
    r"~/Library/LaunchAgents/|"
    r"~/.config/[^/\s]*credentials|"
    r"/\.env\b|\.env\b"
    r")",
    re.IGNORECASE,
)

# Mutating options on nominally-read-only commands
_MUTATING_OPTIONS: dict[str, list[str]] = {
    "find": ["-delete", "-exec", "-execdir", "-ok", "-okdir"],
    "git": ["push", "merge", "rebase", "tag", "add", "commit", "stash", "clean"],
}

# Destructive git commands that must never be auto-approved.
# All forms of checkout that restore/discard working-tree content are covered:
#   git checkout -- path          → discards local changes to path
#   git checkout HEAD -- path     → restores path from HEAD
#   git checkout <rev> -- path    → restores path from any revision
#   git checkout -f               → force checkout, discards changes
#   git checkout --force          → same
#   git restore path              → discards local changes
#   git restore --staged path     → unstages (still destructive in context)
_DESTRUCTIVE_GIT_COMMANDS: re.Pattern[str] = re.compile(
    r"git\s+(?:"
    r"checkout\s+.*--|"           # checkout <anything> -- path  (discards changes)
    r"checkout\s+-f\b|"
    r"checkout\s+--force\b|"
    r"switch\s+-C\b|"
    r"switch\s+--force-create\b|"
    r"switch\s+--discard-changes\b|"
    r"restore\b|"
    r"branch\s+-D\b|"
    r"stash\s+drop\b|"
    r"stash\s+clear\b|"
    r"clean\b|"
    r"reset\s+--hard|"
    r"reflog\s+expire"
    r")"
)

# Sensitive paths — reading these must never be R0.
#
# Thread 2 (Codex V12): Comprehensive credential path coverage.
# Every path form (tilde, $HOME, ${HOME}, /root, /home/*, /Users/*)
# must be covered for .aws, .ssh, .npmrc, .docker/config.json,
# .config/gh/hosts.yml, .netrc, .pypirc, .git-credentials.
_SENSITIVE_PATH_PATTERNS: re.Pattern[str] = re.compile(
    r"(?:"
    # ── ~/ tilde forms ──
    r"~/.ssh/|"
    r"~/.aws/|"
    r"~/.npmrc\b|"
    r"~/.docker/config\.json|"
    r"~/.config/gh/hosts\.yml|"
    r"~/.config/[^/\s]*credentials|"
    r"~/.netrc\b|"
    r"~/.pypirc\b|"
    r"~/.git-credentials\b|"
    r"~/Library/Keychains/|"
    # ── $HOME / ${HOME} forms ──
    r"\$HOME/\.ssh/|"
    r"\$HOME/\.aws/|"
    r"\$HOME/\.npmrc\b|"
    r"\$HOME/\.docker/config\.json|"
    r"\$\{HOME\}/\.ssh/|"
    r"\$\{HOME\}/\.aws/|"
    r"\$\{HOME\}/\.npmrc\b|"
    r"\$\{HOME\}/\.docker/config\.json|"
    # ── Absolute paths to user credential directories (macOS + Linux) ──
    r"/home/[^/\s]+/\.ssh/|"
    r"/home/[^/\s]+/\.aws/|"
    r"/home/[^/\s]+/\.npmrc\b|"
    r"/home/[^/\s]+/\.docker/config\.json|"
    r"/Users/[^/\s]+/\.ssh/|"
    r"/Users/[^/\s]+/\.aws/|"
    r"/Users/[^/\s]+/\.npmrc\b|"
    r"/Users/[^/\s]+/\.docker/config\.json|"
    r"/Users/[^/\s]+/Library/Keychains/|"
    # ── Thread 6 (Codex V11) + Thread 2 (Codex V12): /root credential dirs ──
    r"/root/\.ssh/|"
    r"/root/\.aws/|"
    r"/root/\.npmrc\b|"
    r"/root/\.docker/config\.json|"
    # ── Dotfiles / credential files ──
    r"/\.env\b|"
    r"\.env\b|"
    r"\.pem\b|"
    r"\.key\b|"
    r"id_rsa|"
    r"id_ed25519|"
    r"id_ecdsa|"
    r"private_key|"
    r"\.netrc\b|"
    r"\.git-credentials\b|"
    r"Keychain\b|"
    r"keychain\b|"
    # ── /proc/*/environ — reading process environment exposes secrets ──
    r"/proc/self/environ\b|"
    r"/proc/\d+/environ\b|"
    r"/proc/[^/\s]*/environ\b"
    r")",
    re.IGNORECASE,
)

# Secret expansion patterns — commands that could output secrets.
# Detects ALL braced shell parameter expansions (any modifier syntax):
#   ${TOKEN} ${TOKEN:-default} ${TOKEN:=value} ${TOKEN:+alt} ${TOKEN:?err}
#   ${TOKEN#prefix} ${TOKEN##prefix} ${TOKEN%suffix} ${TOKEN%%suffix}
#   ${TOKEN:offset:len} ${TOKEN/pat/repl} ${!TOKEN} ${TOKEN^^} ${TOKEN,,}
# Variable names matching sensitive keywords → immediate R4.
#
# Thread D (Codex V9): Comprehensive braced expansion — catch ALL modifier
# forms by matching ${VARNAME<any non-brace content>} rather than enumerating
# finite modifier syntaxes.  Variable names are checked against a dedicated
# sensitive-keyword pattern to avoid false positives on ${HOME}, ${USER}, etc.
_SENSITIVE_VAR_NAME: re.Pattern[str] = re.compile(
    r"(?:"
    r"TOKEN|SECRET|KEY|PASSWORD|CREDENTIAL|AUTH|PASS|"
    r"GITHUB_TOKEN|NPM_TOKEN|API_KEY|AWS_|AZURE_|GCLOUD_|"
    r"DOCKER_|REGISTRY_|DATABASE_URL|REDIS_URL|MONGO_|PG_|MYSQL_"
    r")",
    re.IGNORECASE,
)

# Match any braced variable expansion: ${VARNAME<any content>}
_BRACED_VAR_EXPANSION: re.Pattern[str] = re.compile(
    r"\$\{([A-Za-z_][A-Za-z0-9_]*)[^}]*\}"
)

# Full secret expansion: echo/printf with $VAR, any braced var with
# sensitive name, env|grep, printenv, bare env
_SECRET_EXPANSION: re.Pattern[str] = re.compile(
    r"(?:"
    r"echo\s+.*\$[A-Za-z_][A-Za-z0-9_]*|"  # echo ... $VAR any position
    r"printf\s+.*\$[A-Za-z_][A-Za-z0-9_]*|" # printf ... $VAR any position
    r"\$\{[A-Za-z_][A-Za-z0-9_]*[^}]*\}|"   # any braced var expansion
    r"\$[A-Z_][A-Z0-9_]{2,}\b|"             # $TOKEN bare (3+ chars)
    # Thread 10 (Codex V10): Anchor true env command, not "venv"
    r"(?:^|[\s;&|])env(?:\s+\S|\s*$)|"       # env command (must be standalone or with args)
    r"(?:^|[\s;&|])/usr/bin/env(?:\s+\S|\s*$)|"  # absolute env path
    r"\bprintenv\s+[A-Za-z_][A-Za-z0-9_]*|" # printenv TOKEN
    r"\bprintenv\b"                          # bare printenv
    r")",
)


def _has_control_operators(command: str) -> bool:
    """True if the command contains shell control operators (;, &&, ||, |, &, \\n)."""
    return bool(_CONTROL_OPERATORS.search(command))


def _has_redirection(command: str) -> bool:
    """True if the command contains output redirection (> , >>, &>, 2>)."""
    return bool(_REDIRECTION_PATTERN.search(command))


def _has_command_substitution(command: str) -> bool:
    """True if the command contains $(...) or backtick command substitution."""
    return bool(_COMMAND_SUBSTITUTION.search(command))


def _has_process_substitution(command: str) -> bool:
    """True if the command contains <(cmd) or >(cmd) process substitution."""
    return bool(_PROCESS_SUBSTITUTION.search(command))


def _has_mutating_option(command: str, base_cmd: str) -> bool:
    """True if *base_cmd* is used with a known mutating option.

    Thread 6 (Codex V12): For git commands, checks the ACTUAL subcommand
    (token-parsed) rather than substring-matching the full command string.
    This prevents false positives like:
      git branch --list feature/merge-ui  → 'merge' in branch name
      git log --grep=commit               → 'commit' in grep pattern
    """
    if base_cmd == "git":
        sub = _parse_git_subcommand(command)
        if sub is None:
            return False
        options = _MUTATING_OPTIONS.get(base_cmd, [])
        return sub in options
    options = _MUTATING_OPTIONS.get(base_cmd, [])
    for opt in options:
        if opt in command:
            return True
    return False


def _is_destructive_git(command: str) -> bool:
    """True if the command is a destructive git operation.

    Thread H (Codex V9): Also catches 'git checkout <rev> <path>' without '--'
    (e.g. 'git checkout HEAD README.md' restores a file and discards changes).
    Uses token-based detection: if 'checkout' is followed by a revision-like
    token and then a path-like token with no intervening '--', it's destructive.

    Thread 3 (Codex V12): Also catches single-arg path-only checkout
    (e.g. 'git checkout README.md', 'git checkout .', 'git checkout ./src/a.py').
    """
    if _DESTRUCTIVE_GIT_COMMANDS.search(command):
        return True
    # Detect checkout <revision> <path> without --
    if _checkout_without_dashdash(command):
        return True
    # Detect single-arg path-only checkout
    if _is_path_like_checkout(command):
        return True
    return False


def _checkout_without_dashdash(command: str) -> bool:
    """Detect 'git checkout <tree-ish> <path>' without '--'.

    Thread 5 (Codex V10) + Thread 1 (Codex V11): ANY git checkout with 2+
    non-flag, non-option arguments where '--' is absent is a destructive
    restore.  Single-argument checkout (branch switch) remains R2.

    Covers:
      git checkout main README.md          → destructive
      git checkout feature/foo src/a.py    → destructive
      git checkout HEAD~1 README.md        → destructive
      git checkout main                    → branch switch (R2, not caught)
      git checkout -b new-branch           → create branch (not caught)
    """
    try:
        tokens = __import__("shlex").split(command)
    except ValueError:
        tokens = command.split()
    if len(tokens) < 4:
        return False
    if tokens[0] != "git" or tokens[1] != "checkout":
        return False
    if "--" in tokens:
        return False
    # Any non-flag arg after checkout that isn't an option is a tree-ish
    args = [t for t in tokens[2:] if not t.startswith("-")]
    if len(args) < 2:
        return False
    # Two or more non-flag arguments with no '--' → destructive restore.
    # Every branch name, tag, commit SHA, or ref is a valid tree-ish.
    return True


def _is_path_like_checkout(command: str, cwd: str = "") -> bool:
    """Detect 'git checkout <single-path-arg>' (path-only restore, not branch switch).

    Thread 3 (Codex V12): Single-argument 'git checkout' with a path-like
    argument is a destructive file restore, not a branch switch.  Must be R3/R4.

    Covers:
      git checkout README.md       → destructive (file exists in worktree)
      git checkout .               → destructive (discards all changes)
      git checkout src/file.py     → destructive (path contains /)
      git checkout ./path           → destructive (starts with ./)
      git checkout ../path          → destructive (starts with ../)
      git checkout -- README.md     → destructive (explicit -- separator)
      git checkout main             → branch switch (doesn't look path-like)

    When the argument could be either a branch name or a path (e.g. 'src/main'),
    fail closed → treat as destructive.
    """
    import os as _os
    import re as _re

    try:
        tokens = __import__("shlex").split(command)
    except ValueError:
        tokens = command.split()
    if len(tokens) < 3:
        return False
    if tokens[0] != "git" or tokens[1] != "checkout":
        return False

    # 'git checkout -- <path>' → always destructive
    if "--" in tokens:
        return True

    # Collect non-flag arguments after 'checkout'
    args = [t for t in tokens[2:] if not t.startswith("-")]
    if len(args) != 1:
        return False  # 0 args or 2+ args handled elsewhere

    arg = args[0]

    # Explicit path indicators → always destructive
    if arg in (".", ".."):
        return True
    if arg.startswith("./") or arg.startswith("../"):
        return True

    # Contains a path separator → likely a path, not a branch
    if "/" in arg:
        # Branch names can also contain '/', so check if it exists in worktree
        if cwd:
            candidate = _os.path.join(cwd, arg)
            if _os.path.lexists(candidate):
                return True
            # Also check relative to repo root
            if _os.path.lexists(arg):
                return True
        # Path-like with '/' → fail closed as destructive
        return True

    # File extension that's clearly not a branch → likely a path
    # (branches rarely have extensions like .md, .py, .js, etc.)
    if _os.path.splitext(arg)[1] in (
        ".md", ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yaml", ".yml",
        ".toml", ".cfg", ".ini", ".txt", ".css", ".html", ".rs", ".go",
        ".java", ".c", ".cpp", ".h", ".hpp", ".rb", ".php", ".swift",
    ):
        return True

    # Check if it exists as a file/directory in the filesystem
    if cwd:
        candidate = _os.path.join(cwd, arg)
        if _os.path.lexists(candidate):
            return True
    if _os.path.lexists(arg):
        return True

    # Unknown single arg — could be branch or path.  Fail closed.
    # If it looks like a valid branch name pattern (no spaces, no wildcards,
    # starts with letter/_), treat as branch switch.  Otherwise destructive.
    if _re.match(r'^[a-zA-Z_][a-zA-Z0-9_./-]*$', arg) and "/" not in arg:
        return False  # simple branch name like 'main', 'develop'

    return True  # fail closed — ambiguous single arg


def _reads_sensitive_path(command: str, cwd: str = "") -> bool:
    """True if the command reads any sensitive paths.

    Thread G (Codex V9): When cwd itself is a sensitive directory
    (e.g. ~/.ssh, ~/.aws), relative file reads like 'cat id_rsa' or
    'cat credentials' resolve to sensitive targets.
    """
    if _SENSITIVE_PATH_PATTERNS.search(command):
        return True
    # CWD-aware: if cwd is sensitive, any relative file read is dangerous
    if cwd and _cwd_is_sensitive(cwd):
        # Check for read commands with relative paths
        if _has_relative_file_read(command):
            return True
    return False


# Sensitive CWD patterns — directories where reading any file is R4.
# Thread 2 (Codex V12): Extended to cover .npmrc, .docker, .config/gh, .netrc, .pypirc.
_SENSITIVE_CWD: re.Pattern[str] = re.compile(
    r"(?:"
    r"/\.ssh|/\.aws|/\.npmrc|/\.docker|"
    r"/\.config/gh|/\.netrc|/\.pypirc|"
    r"/\.config/[^/\s]*credentials|"
    r"/Library/Keychains|"
    r"/root/\.ssh|/root/\.aws|/root/\.npmrc|/root/\.docker"
    r")",
    re.IGNORECASE,
)


def _cwd_is_sensitive(cwd: str) -> bool:
    """True if the working directory itself is a credential directory.

    Thread 2 (Codex V12): Normalises $HOME and ${HOME} before checking
    so cwd-relative access through environment variables is also caught.
    """
    import os
    resolved = os.path.expanduser(cwd)
    # Expand $HOME and ${HOME} env var references
    resolved = _expand_home_env_vars(resolved)
    return bool(_SENSITIVE_CWD.search(resolved))


def _expand_home_env_vars(path: str) -> str:
    """Expand $HOME and ${HOME} references in a path string.

    Thread 2 (Codex V12): Commands like 'cat $HOME/.aws/credentials' must be
    detected even when the literal $HOME appears in the path string.
    """
    import os as _os
    home = _os.environ.get("HOME", "")
    if not home:
        return path
    result = path.replace("${HOME}", home).replace("$HOME", home)
    return result


# Common read commands that take a file path as first non-flag argument
_READ_COMMANDS: re.Pattern[str] = re.compile(
    r"^(?:cat|head|tail|less|more|grep|rg|file|stat|ls)\s"
)


def _has_relative_file_read(command: str) -> bool:
    """True if command is a read command with a relative path argument."""
    if not _READ_COMMANDS.match(command):
        return False
    try:
        tokens = __import__("shlex").split(command)
    except ValueError:
        tokens = command.split()
    # Check for relative path arguments (no leading /, no ~, no $)
    for token in tokens[1:]:
        if token.startswith("-"):
            continue
        if token.startswith("/") or token.startswith("~") or "$" in token:
            continue
        # Looks like a relative file path → dangerous in sensitive CWD
        return True
    return False


def _writes_unsafe_target(command: str) -> bool:
    """True if touch/cp/mv targets a sensitive system/user path.

    Thread 6 (Codex V10): Writing to ~/.bashrc, ~/.ssh, /etc, ~/Library/...
    must be R3/R4.  Project-workspace writes remain R2.
    """
    if not _UNSAFE_WRITE_TARGETS.search(command):
        return False
    # Check that we have a write command (touch/cp/mv), not a read
    if not re.search(r"(?:^|\s)(?:touch|cp|mv)\s", command):
        return False
    return True


def _has_secret_expansion(command: str) -> bool:
    """True if the command could output a secret.

    Thread 2 (Codex V10): Scans ALL expansions (braced AND bare) together.
    A command like 'echo foo $API_KEY ${HOME}' must still be R4 because
    $API_KEY is a bare sensitive expansion, even though ${HOME} is safe.
    The presence of a safe braced expansion must NOT mask a dangerous
    bare expansion.
    """
    # Quick pre-filter — any expansion at all?
    if not _SECRET_EXPANSION.search(command):
        return False
    # Scan ALL braced variable names for sensitive keywords
    braced_matches = _BRACED_VAR_EXPANSION.findall(command)
    if braced_matches and any(_SENSITIVE_VAR_NAME.search(v) for v in braced_matches):
        return True
    # Scan bare $VAR patterns (non-braced)
    bare_vars = _BARE_VAR_EXPANSION.findall(command)
    if bare_vars and any(_SENSITIVE_VAR_NAME.search(v) for v in bare_vars):
        return True
    # echo/printf with any $VAR, env|grep, printenv, bare env → flag
    if braced_matches or bare_vars:
        return False  # had expansions but none sensitive
    return True  # env|grep, printenv, bare env (no var name to check)


# Pattern for bare $VAR expansions (non-braced)
_BARE_VAR_EXPANSION: re.Pattern[str] = re.compile(
    r"\$([A-Za-z_][A-Za-z0-9_]*)"
)


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
    """True if gh api has field/method/input params that make it mutating.

    Detects both space-separated and equals-form flags:
    - -f body=hi, --field body=hi, --field=body=hi
    - -F body=hi, --raw-field key=val, --raw-field=key=val
    - -X POST, -XPOST, --method POST, --method=POST, --method=DELETE
    - --input file.json, --input=file.json (GraphQL mutation bodies)
    """
    # Space-separated: -f value, --field value, -F value, --raw-field value
    if re.search(r"(?:-f|--field|--raw-field)\s", command):
        return True
    if re.search(r"(?:-F)\s", command):
        return True
    # Equals-form: --field=value, --raw-field=value
    if re.search(r"(?:--field|--raw-field)=", command):
        return True
    # --input (space or equals): GraphQL mutation file input
    if re.search(r"--input[\s=]", command):
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


# ── Git subcommand token parsing ──

# Thread 6 (Codex V12): Mutating git subcommands — classified by TOKEN POSITION,
# NOT by substring match.  This prevents false positives on:
#   git log --grep=commit   (commit is in grep pattern, not a subcommand)
#   git diff origin/push-fix (push is in a ref name, not a subcommand)
#   git show commit123       (commit123 is a revision, not a subcommand)
_GIT_MUTATING_SUBCOMMANDS: set[str] = {
    "commit", "push", "merge", "rebase", "reset",
    "checkout", "switch", "tag",
    "clean", "restore", "cherry-pick", "revert",
    "add", "rm", "mv",
}

# Git subcommands that can be either read or write depending on arguments.
# branch --list / stash list → read; branch -d / stash drop → destructive.
# The destructive variants are caught by higher-priority R4/R3 patterns.
_GIT_AMBIGUOUS_SUBCOMMANDS: set[str] = {"branch", "stash"}


def _parse_git_subcommand(command: str) -> str | None:
    """Extract the git subcommand by token position.

    Parses:  git [global-options] <subcommand> [args]

    Skips global options (tokens starting with '-' that appear BEFORE the
    subcommand), including options that consume a following value:
      -C <path>       (run as if git was started in <path>)
      -c <name=value> (pass config parameter)
      --exec-path[=<path>]

    Returns the FIRST non-option positional token after 'git',
    or None if the command string is not a git invocation.
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    if len(tokens) < 2:
        return None
    if tokens[0] != "git":
        return None
    # Options that consume their next token as a value
    _VALUE_OPTIONS = {"-C", "-c", "--exec-path"}
    i = 1
    while i < len(tokens):
        token = tokens[i]
        # Handle --opt=value form (already one token, skip it)
        if token.startswith("-") and "=" in token:
            i += 1
            continue
        # Handle -C <path>, -c <name=value> (skip option + value)
        if token in _VALUE_OPTIONS:
            i += 2  # skip the option and its value
            continue
        # Handle --exec-path <path> (skip option + value)
        if token == "--exec-path":
            i += 2
            continue
        # Handle --long-opt (no value) — skip
        if token.startswith("-"):
            i += 1
            continue
        # First non-option token — this is the subcommand
        return token
    return None


def _git_has_output_flag(command: str) -> bool:
    """True if a git command uses --output to write to a file.

    Thread 5 (Codex V12): git diff/show/log --output=<file> is NOT read-only.
    Detects both --output=<file> and --output <file> forms.
    Must be evaluated BEFORE R0 git read patterns.
    """
    # --output=<file> (equals form)
    if re.search(r"--output[=\s]\S", command):
        return True
    return False


def _git_output_target_is_sensitive(command: str, cwd: str = "") -> bool:
    """True if the --output target is a sensitive/credential path.

    Thread 5 (Codex V12): Writing git output to /etc, ~/.ssh, ~/.aws, etc.
    must be R4 regardless of the git subcommand being nominally read-only.
    """
    m = re.search(r"--output[=\s](\S+)", command)
    if not m:
        return False
    target = m.group(1)
    # Expand any env vars in the target path
    target = _expand_home_env_vars(target)
    if cwd and not target.startswith("/") and not target.startswith("~"):
        target = cwd.rstrip("/") + "/" + target
    # Use the same sensitive path detection
    return bool(_SENSITIVE_PATH_PATTERNS.search(target))


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
        r"curl.*\.com.*secret",
        r"echo\s+\$",
        r"npm\s+publish", r"twine\s+upload",
        r"gh\s+release\s+create", r"git\s+tag",
        r"chmod\s+[0-7]*7", r"chown\b",
        r"git\s+reset\s+--hard", r"git\s+clean\b",
        r"git\s+stash\s+(?:drop|clear)\b", r"git\s+reflog\s+expire",
        r"\bchmod\s+[0-7]*7", r"\bchmod\s+[ugoa][-+=]",
        # Thread 10 (Codex V10): Anchor standalone env/printenv, not venv
        r"(?:^|[\s;&|])env(?:\s|$)", r"(?:^|[\s;&|])printenv(?:\s|$)",
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
        # Package installation = external code execution → R3
        r"\bpip\s+install\b", r"\bpipx\s+install\b",
        r"\bnpm\s+install\b", r"\bpnpm\s+install\b",
        r"\bnpm\s+ci\b",  # installs deps from lockfile, runs lifecycle scripts
        r"\byarn\s+add\b",
        r"\bcargo\s+install\b",
        r"\bscp\b", r"\brsync\s+.*:", r"\bssh\b",
    ]

    # ── R2: Reversible write ──
    R2_PATTERNS: ClassVar[list[str]] = [
        r"git\s+add\b", r"git\s+commit\b", r"git\s+checkout\b",
        r"git\s+switch\b", r"git\s+branch\b", r"git\s+stash\b",
        r"git\s+worktree\b", r"git\s+rebase\b",
        r"pip\s+uninstall\b", r"npm\s+uninstall\b",
        r"mkdir\b", r"touch\b",
        r"Write\b", r"Edit\b",
        r"(?:^|\s)cp\s", r"(?:^|\s)mv\s",
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
        r"npm\s+test\b",
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
        0. Tokenize and scan for shell injection primitives (substitution, expansion, etc.)
        1. Interpreter snippets (python -c, heredocs)
        2. gh api parameter scan
        3. High-risk patterns (R4, R3, R2)
        4. Shell structure scan (control ops, redirections, mutating opts, substitution)
        5. Destructive git + sensitive path detection
        6. R2/R1/R0 pattern matching
        """

        # ── Layer 0: Tokenize + scan for shell injection primitives ──
        try:
            tokens = shlex.split(command)
        except ValueError:
            tokens = command.split()
        base_cmd = tokens[0] if tokens else ""

        # Command substitution ($(...) or backticks) — always at least R3
        if _has_command_substitution(command):
            return CommandClassification(
                command=command, risk_level=RiskLevel.R3,
                kind=CommandKind.SYSTEM, auto_approvable=False,
                reversible=False,
                reason="shell command substitution detected ($(...) or backticks) — fail-closed to R3",
            )

        # Process substitution (<(cmd) or >(cmd)) — always at least R3
        if _has_process_substitution(command):
            return CommandClassification(
                command=command, risk_level=RiskLevel.R3,
                kind=CommandKind.SYSTEM, auto_approvable=False,
                reversible=False,
                reason="shell process substitution detected (<(...) or >(...)) — fail-closed to R3",
            )

        # Secret expansion (echo "$VAR", printf, env|grep TOKEN) — always R4
        if _has_secret_expansion(command):
            return CommandClassification(
                command=command, risk_level=RiskLevel.R4,
                kind=CommandKind.SECRET, auto_approvable=False,
                reversible=False,
                reason="potential secret expansion detected (echo $VAR, printf, env|grep) — R4",
            )

        # Destructive git commands — always at least R3
        if _is_destructive_git(command):
            return CommandClassification(
                command=command, risk_level=RiskLevel.R3,
                kind=CommandKind.GIT, auto_approvable=False,
                reversible=False,
                reason="destructive git operation — fail-closed to R3",
            )

        # Sensitive path reads — at least R3
        # Thread G (Codex V9): CWD-aware — cwd from kwargs flows through
        # to detect relative file reads in sensitive directories
        if _reads_sensitive_path(command, cwd=kwargs.get("cwd", "")):
            return CommandClassification(
                command=command, risk_level=RiskLevel.R4,
                kind=CommandKind.SECRET, auto_approvable=False,
                reversible=False,
                reason="sensitive path read detected (~/.ssh, ~/.aws, credentials, .env, private keys) — R4",
            )

        # ── Layer 0.5: Git --output detection (before R0 classification) ──
        # Thread 5 (Codex V12): git diff/show/log --output=<file> is NOT
        # read-only.  Must be detected BEFORE the R0 git read patterns fire.
        # Sensitive targets → R4; project-internal → R2; external → R3.
        if tokens and tokens[0] == "git" and _git_has_output_flag(command):
            sub = _parse_git_subcommand(command)
            if sub in ("diff", "show", "log"):
                cwd = kwargs.get("cwd", "")
                if _git_output_target_is_sensitive(command, cwd=cwd):
                    return CommandClassification(
                        command=command, risk_level=RiskLevel.R4,
                        kind=CommandKind.WRITE, auto_approvable=False,
                        reversible=False,
                        reason="git output to sensitive/credential path — R4",
                    )
                # Check if output goes outside repo
                m = re.search(r"--output[=\s](\S+)", command)
                if m:
                    target = m.group(1)
                    if target.startswith("/etc/") or target.startswith("/tmp/") or target.startswith("/var/"):
                        return CommandClassification(
                            command=command, risk_level=RiskLevel.R3,
                            kind=CommandKind.WRITE, auto_approvable=False,
                            reversible=False,
                            reason="git output to system/external path — R3",
                        )
                return CommandClassification(
                    command=command, risk_level=RiskLevel.R2,
                    kind=CommandKind.WRITE, auto_approvable=False,
                    reversible=True,
                    reason="git output to file — R2 write, not read-only",
                )

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
            # Check for mutating API params (includes --input for GraphQL mutations)
            if _gh_api_has_mutating_params(command) or _gh_api_has_non_get_method(command):
                return CommandClassification(
                    command=command, risk_level=RiskLevel.R3,
                    kind=CommandKind.NETWORK, auto_approvable=False,
                    reversible=False,
                    reason="gh api with field/method/write/input params — R3, external side effect",
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
                reason="shell control operators detected (;, &&, ||, |, &) — fail-closed to R3",
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

        # ── Layer 4.5: Git subcommand token-based classification ──
        # Thread 6 (Codex V12): Parse git subcommand by TOKEN POSITION, not
        # by substring match.  This correctly handles:
        #   git -C /tmp status              → R0 (global option before subcommand)
        #   git --no-pager diff             → R0
        #   git log --grep=commit           → R0 (commit is grep pattern, not subcommand)
        #   git diff origin/push-fix        → R0 (push in ref name, not subcommand)
        #   git show commit123              → R0 (commit123 is revision, not subcommand)
        #   git branch --list feature/merge-ui → R0 (branch --list is read-only)
        if base_cmd == "git":
            git_sub = _parse_git_subcommand(command)
            if git_sub in _GIT_MUTATING_SUBCOMMANDS:
                # Known mutating subcommand → at least R2
                return CommandClassification(
                    command=command, risk_level=RiskLevel.R2,
                    kind=CommandKind.GIT, auto_approvable=False,
                    reversible=True,
                    reason=f"git {git_sub} — mutating subcommand (token-parsed) → R2",
                )
            elif git_sub in _GIT_AMBIGUOUS_SUBCOMMANDS:
                # branch/stash: read-only variants get R0, mutating → R2+
                if git_sub == "branch":
                    if re.search(r"branch\s+(-d|--delete|-D|-m|--move|-c|--copy)", command):
                        return CommandClassification(
                            command=command, risk_level=RiskLevel.R3,
                            kind=CommandKind.GIT, auto_approvable=False,
                            reversible=False,
                            reason="git branch delete/move — destructive → R3",
                        )
                    if re.search(r"branch\s+(--list|-l|--show-current|--remote|-r|--all|-a|--merged|--no-merged|--contains)", command):
                        return CommandClassification(
                            command=command, risk_level=RiskLevel.R0,
                            kind=CommandKind.GIT, auto_approvable=True,
                            reversible=True,
                            reason="git branch --list (token-parsed) — read-only → R0",
                        )
                    # Plain 'git branch' → list (R0); 'git branch new-name' → create (R2)
                    non_flag = [t for t in tokens[2:] if not t.startswith("-")]
                    if not non_flag:
                        return CommandClassification(
                            command=command, risk_level=RiskLevel.R0,
                            kind=CommandKind.GIT, auto_approvable=True,
                            reversible=True,
                            reason="git branch (list mode, token-parsed) — read-only → R0",
                        )
                    return CommandClassification(
                        command=command, risk_level=RiskLevel.R2,
                        kind=CommandKind.GIT, auto_approvable=False,
                        reversible=True,
                        reason="git branch create — mutating → R2",
                    )
                elif git_sub == "stash":
                    if re.search(r"stash\s+(list|show)", command):
                        return CommandClassification(
                            command=command, risk_level=RiskLevel.R0,
                            kind=CommandKind.GIT, auto_approvable=True,
                            reversible=True,
                            reason="git stash list/show — read-only → R0",
                        )
                    # stash push/pop/apply/drop/clear → already caught by R4/R3 patterns above
                    return CommandClassification(
                        command=command, risk_level=RiskLevel.R2,
                        kind=CommandKind.GIT, auto_approvable=False,
                        reversible=True,
                        reason="git stash — mutating → R2",
                    )
            elif git_sub in ("status", "log", "diff", "show", "rev-parse",
                             "ls-remote", "ls-files", "cat-file", "describe",
                             "fetch", "remote", "config", "blame", "grep"):
                return CommandClassification(
                    command=command, risk_level=RiskLevel.R0,
                    kind=CommandKind.GIT, auto_approvable=True,
                    reversible=True,
                    reason=f"git {git_sub} — read-only subcommand (token-parsed) → R0",
                )

        # ── Layer 5: R2 pattern matching ──
        for pattern in self.R2_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                # Thread 6 (Codex V10): touch/cp/mv to unsafe paths → R3/R4
                if _writes_unsafe_target(command):
                    return CommandClassification(
                        command=command, risk_level=RiskLevel.R3,
                        kind=CommandKind.WRITE, auto_approvable=False,
                        reversible=False,
                        reason="write target is unsafe (~/.ssh, ~/.aws, /etc, /Library, etc.) — R3",
                    )
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
