#!/usr/bin/env python3
"""
NEXARA PRIME — Merge Contract Validator V1

Reads the body of a GitHub pull request and validates that all required
merge contract fields exist and are non-empty.

Usage:
    python3 validate_merge_contract.py --pr-body "| mission_id | MISSION-... | ..."
    python3 validate_merge_contract.py --pr-body-file /path/to/pr_body.md

Exit codes:
    0  — all required fields present and non-empty
    1  — one or more fields missing or empty
    2  — unable to read PR body
"""

import argparse
import re
import sys
from pathlib import Path

# ── Schema (loaded from MERGE_CONTRACT_V1.yaml, inlined for independence) ──

REQUIRED_FIELDS = {
    "mission_id": {
        "pattern": r"^MISSION-\d{4}-\d{3,}$",
        "example": "MISSION-2026-007",
    },
    "program_id": {
        "enum": ["NEXARA_FIRST_PARTY_SOVEREIGN_AGENT"],
    },
    "gate_scope": {
        "pattern": r"^G(?:[0-9]|10)(?:,\s*G(?:[0-9]|10))*$",
        "example": "G7,G8,G10",
    },
    "risk_level": {
        "enum": ["R0", "R1", "R2", "R3", "R4"],
    },
    "changed_modules": {
        "min_length": 1,
        "example": "nexara_prime/cli, platform/sdk/typescript",
    },
    "test_summary": {
        "pattern": r"^\d+ passed, \d+ failed",
        "example": "517 passed, 0 failed",
    },
    "evidence_refs": {
        "min_length": 1,
        "example": "reports/program/G10/evidence.md",
    },
    "rollback_plan": {
        "min_length": 20,
        "example": "git revert <SHA> and restore previous .nexara state",
    },
    "external_dependencies": {
        "min_length": 1,
        "example": "macOS code signing certificate (Apple Developer Program)",
    },
}

RISK_LEVELS = ["R0", "R1", "R2", "R3", "R4"]


def parse_pr_body(body: str) -> dict[str, str]:
    """Extract merge contract fields from a PR body Markdown table."""
    fields: dict[str, str] = {}

    # Pattern: | **field_name** | value |
    # The PR template uses: | **field_name** | <!-- comment or value --> |
    table_pattern = re.compile(
        r"\|\s*\*\*(?P<key>[a-z_]+)\*\*\s*\|\s*(?P<value>[^|]*?)\s*\|",
        re.IGNORECASE | re.MULTILINE,
    )

    for match in table_pattern.finditer(body):
        key = match.group("key").strip().lower()
        value = match.group("value").strip()
        # Strip HTML comments <!-- ... -->
        value = re.sub(r"<!--.*?-->", "", value).strip()
        if value:
            fields[key] = value

    return fields


def validate_field(
    key: str, value: str, rules: dict
) -> list[str]:
    """Validate a single field against its rules. Returns list of error messages."""
    errors: list[str] = []

    if not value or value == "N/A":
        errors.append(f"{key}: field is empty or set to N/A")
        return errors

    # Enum check
    if "enum" in rules:
        allowed = rules["enum"]
        if value not in allowed:
            errors.append(
                f"{key}: '{value}' is not valid; must be one of {allowed}"
            )

    # Pattern check
    if "pattern" in rules:
        if not re.match(rules["pattern"], value):
            errors.append(
                f"{key}: does not match required pattern "
                f"'{rules['pattern']}' (example: {rules.get('example', 'N/A')})"
            )

    # Min length check
    if "min_length" in rules and len(value) < rules["min_length"]:
        errors.append(
            f"{key}: too short ({len(value)} chars); "
            f"minimum {rules['min_length']} characters required"
        )

    return errors


def validate_contract(body: str) -> tuple[bool, list[str]]:
    """
    Validate a PR body against the merge contract schema.

    Returns (is_valid, list_of_error_messages).
    """
    errors: list[str] = []
    fields = parse_pr_body(body)

    if not fields:
        errors.append(
            "Could not parse any merge contract fields from PR body. "
            "Ensure the PR template is used."
        )
        return False, errors

    # Check each required field
    for key, rules in REQUIRED_FIELDS.items():
        value = fields.get(key, "")
        field_errors = validate_field(key, value, rules)
        errors.extend(field_errors)

    # Check for unknown fields (optional: warn only)
    unknown = set(fields.keys()) - set(REQUIRED_FIELDS.keys())
    if unknown:
        # These are not errors but could indicate a template mismatch
        pass

    # Risk-level consistency check
    risk = fields.get("risk_level", "")
    gate_scope = fields.get("gate_scope", "")
    if risk in ("R3", "R4") and not gate_scope:
        errors.append(
            "R3/R4 changes must specify at least one gate in gate_scope"
        )

    return len(errors) == 0, errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate NEXARA PRIME merge contract fields in a PR body."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--pr-body",
        type=str,
        help="Inline PR body text",
    )
    source.add_argument(
        "--pr-body-file",
        type=str,
        help="Path to a file containing the PR body text",
    )
    args = parser.parse_args()

    if args.pr_body_file:
        path = Path(args.pr_body_file)
        if not path.exists():
            print(f"ERROR: PR body file not found: {path}", file=sys.stderr)
            return 2
        body = path.read_text(encoding="utf-8")
    else:
        body = args.pr_body

    valid, errors = validate_contract(body)

    if valid:
        print("MERGE CONTRACT VALID: all required fields present and valid.")
        return 0
    else:
        print("MERGE CONTRACT INVALID:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
