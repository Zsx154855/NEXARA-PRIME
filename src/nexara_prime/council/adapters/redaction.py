"""NEXARA Council V2 — Secret Redaction

Ensures no credential data leaks into logs, evidence, or adapter output.
All adapters MUST use this module before recording any response data.
"""

from __future__ import annotations

import re

# Patterns that indicate secrets — redacted from all output
_SECRET_PATTERNS: list[tuple[str, str]] = [
    (r'sk-[A-Za-z0-9]{20,}', '[REDACTED:OPENAI_KEY]'),
    (r'sk-ant-[A-Za-z0-9]{20,}', '[REDACTED:ANTHROPIC_KEY]'),
    (r'xai-[A-Za-z0-9]{20,}', '[REDACTED:XAI_KEY]'),
    (r'sk-[a-z0-9]{32,}', '[REDACTED:API_KEY]'),
    (r'Bearer\s+[A-Za-z0-9_\-\.]+', '[REDACTED:AUTH_HEADER]'),
    (r'Authorization:\s*[A-Za-z0-9_\-\.]+', '[REDACTED:AUTH_HEADER]'),
    (r'api[_-]?key[=:]\s*[A-Za-z0-9_\-]+', '[REDACTED:API_KEY_PARAM]'),
    (r'ghp_[A-Za-z0-9]{36}', '[REDACTED:GITHUB_TOKEN]'),
    (r'gho_[A-Za-z0-9]{36}', '[REDACTED:GITHUB_OAUTH]'),
    (r'xox[bpras]-[A-Za-z0-9\-]+', '[REDACTED:SLACK_TOKEN]'),
    (r'AIza[0-9A-Za-z\-_]{35}', '[REDACTED:GOOGLE_KEY]'),
]


def redact(text: str) -> str:
    """Redact all known secret patterns from text.

    Returns the text with secrets replaced by [REDACTED:*] markers.
    Never raises — always returns a string, even on non-string input.
    """
    if not isinstance(text, str):
        return str(text)

    result = text
    for pattern, replacement in _SECRET_PATTERNS:
        result = re.sub(pattern, replacement, result)
    return result


def is_clean(text: str) -> bool:
    """Check if text contains no detectable secrets.

    Returns True if no secret patterns found.
    """
    if not isinstance(text, str):
        return True

    for pattern, _ in _SECRET_PATTERNS:
        if re.search(pattern, text):
            return False
    return True


def find_secrets(text: str) -> list[str]:
    """Find and return list of detected secret types (redacted descriptions only).

    Never returns the actual secret values.
    """
    if not isinstance(text, str):
        return []

    found: list[str] = []
    for pattern, replacement in _SECRET_PATTERNS:
        if re.search(pattern, text):
            found.append(replacement)
    return found


def sanitize_for_evidence(data: dict) -> dict:
    """Recursively sanitize a dict for evidence storage.

    Redacts all string values and truncates long strings.
    Never modifies the original dict.
    """
    import copy
    result = copy.deepcopy(data)

    def _sanitize(obj):
        if isinstance(obj, dict):
            return {k: _sanitize(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [_sanitize(v) for v in obj]
        elif isinstance(obj, str):
            redacted = redact(obj)
            if len(redacted) > 500:
                return redacted[:500] + "...[TRUNCATED]"
            return redacted
        return obj

    return _sanitize(result)


def validate_no_secrets_in_evidence(evidence: dict) -> tuple[bool, list[str]]:
    """Validate that evidence dict contains no secrets.

    Returns (is_clean, list_of_found_secret_types).
    """
    all_text = str(evidence)
    found = find_secrets(all_text)
    return len(found) == 0, found
