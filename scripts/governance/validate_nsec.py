#!/usr/bin/env python3
"""NEXARA PRIME — NSEC Governance Integrity Validator.

Validates the NEXARA Sovereign Engineering Constitution (NSEC) ecosystem:
canonical document, machine-readable declaration, Authority Index, agent
bindings, Program Constitution subordination, One-pass Skill binding, and
absence of conflicting supreme authorities.

Exit codes:
    0 — all NSEC integrity checks pass
    1 — one or more NSEC integrity violations detected
    2 — validator could not complete (missing files, parse errors)
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(os.environ.get("NEXARA_ROOT", Path(__file__).resolve().parent.parent.parent))

# ── Scan boundary: directories excluded from recursive scans ──────────────────
IGNORED_DIR_NAMES = {".git", ".worktrees", ".venv", "node_modules", "__pycache__", "dist", "build"}


def _is_ignored_path(path: Path) -> bool:
    """True if any parent directory (or the path itself) is in the ignore set.

    Paths are checked relative to REPO_ROOT to avoid false matches when
    the checkout directory itself contains an ignored directory name.
    """
    try:
        rel = path.resolve().relative_to(REPO_ROOT.resolve())
    except ValueError:
        for part in path.parts:
            if part in IGNORED_DIR_NAMES:
                return True
        return False
    for part in rel.parts:
        if part in IGNORED_DIR_NAMES:
            return True
    return False


def _filter_scan_files(files: list) -> list:
    """Filter out files under ignored directories (e.g. .worktrees)."""
    return [f for f in files if not _is_ignored_path(f)]


# ── Canonical paths ───────────────────────────────────────────────────────────
NSEC_CANONICAL = REPO_ROOT / "governance" / "NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1.md"
NSEC_CANONICAL_V1_SUPERSEDED = REPO_ROOT / "governance" / "NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V1.md"
NSEC_YAML = REPO_ROOT / "governance" / "nsec.yaml"
AUTHORITY_INDEX = REPO_ROOT / "governance" / "authority_index.yaml"
PROGRAM_CONSTITUTION = REPO_ROOT / "NEXARA_PROGRAM_CONSTITUTION_V1.md"
ONEPASS_SKILL = REPO_ROOT / ".qoder" / "skills" / "nexara-sovereign-onepass-program" / "SKILL.md"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"

# ── Expected bindings ─────────────────────────────────────────────────────────
REQUIRED_AGENT_BINDINGS: list[dict[str, Any]] = [
    {
        "path": ".qoder/skills/nexara-sovereign-onepass-program/SKILL.md",
        "description": "One-pass Program Skill",
        "must_contain": "NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1.md",
    },
]

REQUIRED_PROGRAM_CONSTITUTION_DECLARATION = "subordinate to the"
REQUIRED_PROGRAM_CONSTITUTION_NSEC_REF = "NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1.md"

# ── Forbidden patterns ────────────────────────────────────────────────────────
FORBIDDEN_SUPREME_MARKERS = [
    "authority_level: supreme",
    "authority_level:supreme",
    "Authority Level: SUPREME",
    "最高工程治理",
    "single highest engineering governance",
]

# NSEC canonical path stem for matching
NSEC_PATH_STEM = "governance/NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION"


def _read_text(path: Path) -> str:
    """Read file contents as UTF-8 text."""
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    return path.read_text(encoding="utf-8")


def _compute_sha256(path: Path) -> str:
    """Compute SHA256 hex digest of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_yaml_simple(text: str) -> dict[str, Any]:
    """Parse a simple YAML file using only stdlib.

    This is a minimal parser sufficient for nsec.yaml and authority_index.yaml.
    It handles the subset of YAML those files use: top-level scalars, lists,
    and nested mappings. It does NOT handle YAML anchors, aliases, multi-line
    strings (|, >), or complex flow structures.
    """
    try:
        import yaml
        return yaml.safe_load(text)
    except ImportError:
        pass

    # Fallback: minimal YAML parser for our constrained subset
    result: dict[str, Any] = {}
    indent_stack: list[tuple[int, str, Any]] = []  # (indent, key, container)

    for raw_line in text.split("\n"):
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue

        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        # Pop stack to correct indent level
        while indent_stack and indent_stack[-1][0] >= indent:
            indent_stack.pop()

        if ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip()

            if value == "":
                # Nested mapping or list starts
                container: dict[str, Any] | list[Any]
                # Check if next non-comment line starts with "- "
                container = {}  # default to dict
                target = result
                if indent_stack:
                    target = indent_stack[-1][2]
                target[key] = container
                indent_stack.append((indent, key, container))
            elif value.startswith("[") and value.endswith("]"):
                # Inline list
                items = [v.strip().strip("'\"") for v in value[1:-1].split(",") if v.strip()]
                target = result
                if indent_stack:
                    target = indent_stack[-1][2]
                target[key] = items
            else:
                # Scalar value
                val: Any = value.strip("'\"")

                # Boolean conversion
                if val.lower() in ("true", "yes"):
                    val = True
                elif val.lower() in ("false", "no"):
                    val = False
                # Integer conversion
                elif val.isdigit():
                    val = int(val)

                target = result
                if indent_stack:
                    target = indent_stack[-1][2]
                target[key] = val
        elif stripped.startswith("- "):
            # List item
            item_value = stripped[2:].strip().strip("'\"")
            if indent_stack and isinstance(indent_stack[-1][2], list):
                indent_stack[-1][2].append(item_value)
            elif indent_stack and isinstance(indent_stack[-1][2], dict):
                # List under a key not yet started as list
                parent_key = indent_stack[-1][1]
                parent_target = result
                if len(indent_stack) >= 2:
                    parent_target = indent_stack[-2][2]
                parent_target[parent_key] = [item_value]
                indent_stack[-1] = (indent_stack[-1][0], indent_stack[-1][1], parent_target[parent_key])

    return result


# ── Validation Functions ──────────────────────────────────────────────────────


def check_canonical_exists() -> list[str]:
    """Verify the canonical NSEC document exists and is readable."""
    issues: list[str] = []
    if not NSEC_CANONICAL.exists():
        issues.append(f"Canonical NSEC document not found: {NSEC_CANONICAL}")
        return issues
    try:
        _read_text(NSEC_CANONICAL)
    except Exception as exc:
        issues.append(f"Cannot read canonical NSEC: {exc}")
    return issues


def check_machine_declaration() -> list[str]:
    """Verify nsec.yaml exists, is valid, and matches canonical document."""
    issues: list[str] = []
    if not NSEC_YAML.exists():
        issues.append(f"Machine-readable NSEC declaration not found: {NSEC_YAML}")
        return issues

    try:
        text = _read_text(NSEC_YAML)
        declaration = _parse_yaml_simple(text)
    except Exception as exc:
        issues.append(f"Cannot parse nsec.yaml: {exc}")
        return issues

    # Required fields
    required = ["id", "short_name", "version", "status", "authority_level",
                "canonical_document", "canonical_hash"]
    for field in required:
        if field not in declaration:
            issues.append(f"nsec.yaml missing required field: {field}")

    # ID consistency
    decl_id = declaration.get("id", "")
    if decl_id != "NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1":
        issues.append(f"nsec.yaml id mismatch: got '{decl_id}', expected 'NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1'")

    # Authority level
    authority = declaration.get("authority_level", "")
    if authority != "supreme":
        issues.append(f"nsec.yaml authority_level must be 'supreme', got '{authority}'")

    # Status
    status = declaration.get("status", "")
    if status != "ACTIVE":
        issues.append(f"nsec.yaml status must be 'ACTIVE', got '{status}'")

    # Canonical document path
    canon_path = declaration.get("canonical_document", "")
    if canon_path != "governance/NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1.md":
        issues.append(f"nsec.yaml canonical_document path mismatch: '{canon_path}'")

    # Hash verification
    if NSEC_CANONICAL.exists():
        actual_hash = _compute_sha256(NSEC_CANONICAL)
        declared_hash_raw = declaration.get("canonical_hash", "")
        # Support "sha256:<hex>" and bare "<hex>" formats
        if declared_hash_raw.startswith("sha256:"):
            declared_hash = declared_hash_raw[7:]
        else:
            declared_hash = declared_hash_raw
        if declared_hash != actual_hash:
            issues.append(
                f"nsec.yaml canonical_hash mismatch: declared={declared_hash[:16]}..., "
                f"actual={actual_hash[:16]}..."
            )

    # Short name
    short_name = declaration.get("short_name", "")
    if short_name != "NSEC":
        issues.append(f"nsec.yaml short_name must be 'NSEC', got '{short_name}'")

    return issues


def check_authority_index() -> list[str]:
    """Verify authority_index.yaml exists, is valid, and places NSEC correctly."""
    issues: list[str] = []
    if not AUTHORITY_INDEX.exists():
        issues.append(f"Authority Index not found: {AUTHORITY_INDEX}")
        return issues

    try:
        text = _read_text(AUTHORITY_INDEX)
    except Exception as exc:
        issues.append(f"Cannot parse authority_index.yaml: {exc}")
        return issues

    # Must contain NSEC reference
    text_lower = text.lower()
    if "nsec" not in text_lower and "sovereign engineering constitution" not in text_lower:
        issues.append("Authority Index does not reference NSEC")

    # Must contain Reality Override / Tier 0
    if "reality" not in text_lower or ("tier: 0" not in text and "tier:0" not in text):
        issues.append("Authority Index missing Reality Override (Tier 0)")

    return issues


def check_program_constitution_subordination() -> list[str]:
    """Verify Program Constitution declares subordination to NSEC."""
    issues: list[str] = []
    if not PROGRAM_CONSTITUTION.exists():
        issues.append(f"Program Constitution not found: {PROGRAM_CONSTITUTION}")
        return issues

    try:
        text = _read_text(PROGRAM_CONSTITUTION)
    except Exception as exc:
        issues.append(f"Cannot read Program Constitution: {exc}")
        return issues

    if REQUIRED_PROGRAM_CONSTITUTION_DECLARATION not in text:
        issues.append(
            "Program Constitution does not declare subordination to NSEC. "
            f"Expected text containing: '{REQUIRED_PROGRAM_CONSTITUTION_DECLARATION}'"
        )

    if REQUIRED_PROGRAM_CONSTITUTION_NSEC_REF not in text:
        issues.append(
            "Program Constitution does not reference NSEC canonical document. "
            f"Expected reference to: '{REQUIRED_PROGRAM_CONSTITUTION_NSEC_REF}'"
        )

    return issues


def check_onepass_skill_binding() -> list[str]:
    """Verify One-pass Program Skill references canonical NSEC."""
    issues: list[str] = []
    if not ONEPASS_SKILL.exists():
        issues.append(f"One-pass Skill not found: {ONEPASS_SKILL}")
        return issues

    try:
        text = _read_text(ONEPASS_SKILL)
    except Exception as exc:
        issues.append(f"Cannot read One-pass Skill: {exc}")
        return issues

    if REQUIRED_PROGRAM_CONSTITUTION_NSEC_REF not in text:
        issues.append(
            "One-pass Skill does not reference NSEC canonical document. "
            f"Expected reference to: '{REQUIRED_PROGRAM_CONSTITUTION_NSEC_REF}'"
        )

    return issues


def check_agent_bindings() -> list[str]:
    """Verify all required agent/skill entries reference NSEC."""
    issues: list[str] = []
    for binding in REQUIRED_AGENT_BINDINGS:
        path = REPO_ROOT / binding["path"]
        if not path.exists():
            issues.append(f"Agent binding target not found: {path}")
            continue
        try:
            text = _read_text(path)
        except Exception as exc:
            issues.append(f"Cannot read {path}: {exc}")
            continue

        must_contain = binding["must_contain"]
        if must_contain not in text:
            issues.append(
                f"{binding['description']} ({binding['path']}) does not reference NSEC. "
                f"Expected text containing: '{must_contain}'"
            )

    return issues


def check_no_duplicate_supreme_authority() -> list[str]:
    """Verify no other file claims supreme governance authority."""
    issues: list[str] = []
    scan_dirs = [
        REPO_ROOT / "governance",
        REPO_ROOT / "docs",
    ]
    # Also check root-level markdown and yaml files
    scan_files: list[Path] = []
    for scan_dir in scan_dirs:
        if scan_dir.exists():
            scan_files.extend(_filter_scan_files(list(scan_dir.rglob("*.md"))))
            scan_files.extend(_filter_scan_files(list(scan_dir.rglob("*.yaml"))))
            scan_files.extend(_filter_scan_files(list(scan_dir.rglob("*.yml"))))
    scan_files.extend(REPO_ROOT.glob("*.md"))
    scan_files.extend(REPO_ROOT.glob("*.yaml"))

    for file_path in scan_files:
        # Skip the canonical NSEC itself and its machine declaration
        if file_path.resolve() == NSEC_CANONICAL.resolve():
            continue
        if file_path.resolve() == NSEC_CANONICAL_V1_SUPERSEDED.resolve():
            continue
        if file_path.resolve() == NSEC_YAML.resolve():
            continue
        if file_path.resolve() == AUTHORITY_INDEX.resolve():
            continue
        # Skip the Program Constitution (already verified for subordination)
        if file_path.resolve() == PROGRAM_CONSTITUTION.resolve():
            continue

        try:
            text = _read_text(file_path)
        except Exception:
            continue

        text_lower = text.lower()
        for marker in FORBIDDEN_SUPREME_MARKERS:
            if marker.lower() in text_lower:
                # Check context: is it a reference to NSEC or a competing claim?
                # A competing claim uses the marker as a self-description
                if "this document" in text_lower or "this file" in text_lower or \
                   "this constitution" in text_lower or "this policy" in text_lower:
                    issues.append(
                        f"File '{file_path.relative_to(REPO_ROOT)}' appears to claim "
                        f"supreme governance authority (marker: '{marker}'). "
                        f"Only NSEC may claim supreme authority."
                    )
                    break

    return issues


def check_ci_binding() -> list[str]:
    """Verify CI workflow includes NSEC Governance Integrity job."""
    issues: list[str] = []
    if not CI_WORKFLOW.exists():
        issues.append(f"CI workflow not found: {CI_WORKFLOW}")
        return issues

    try:
        text = _read_text(CI_WORKFLOW)
    except Exception as exc:
        issues.append(f"Cannot read CI workflow: {exc}")
        return issues

    if "validate_nsec.py" not in text:
        issues.append(
            "CI workflow does not include NSEC validation (validate_nsec.py). "
            "The NSEC Governance Integrity job must be present."
        )

    if "NSEC Governance Integrity" not in text and "nsec" not in text.lower():
        issues.append(
            "CI workflow does not contain an NSEC Governance Integrity job."
        )

    return issues


def check_broken_references() -> list[str]:
    """Verify no broken references to NSEC or Authority Index exist."""
    issues: list[str] = []
    # Check that files referenced in nsec.yaml exist
    if NSEC_YAML.exists():
        try:
            text = _read_text(NSEC_YAML)
            declaration = _parse_yaml_simple(text)
        except Exception:
            declaration = {}

        # Check validator and drift detector paths
        for key in ("validator", "drift_detector"):
            verification = declaration.get("verification", {})
            if isinstance(verification, dict):
                path_str = verification.get(key, "")
                if path_str and not (REPO_ROOT / path_str).exists():
                    issues.append(f"nsec.yaml references non-existent {key}: {path_str}")

    return issues


def check_copy_drift() -> list[str]:
    """Detect if NSEC content has been copied (drifted) to other files."""
    issues: list[str] = []
    if not NSEC_CANONICAL.exists():
        return issues

    # Scan for NSEC content copies
    scan_dirs = [
        REPO_ROOT / "docs",
        REPO_ROOT / "skills",
        REPO_ROOT / ".qoder",
        REPO_ROOT / "reports",
        REPO_ROOT,
    ]

    for scan_dir in scan_dirs:
        if not scan_dir.exists():
            continue
        for md_file in _filter_scan_files(list(scan_dir.rglob("*.md"))):
            if md_file.resolve() == NSEC_CANONICAL.resolve():
                continue
            if md_file.resolve() == NSEC_CANONICAL_V1_SUPERSEDED.resolve():
                continue
            if md_file.resolve() == PROGRAM_CONSTITUTION.resolve():
                continue
            if md_file.resolve() == ONEPASS_SKILL.resolve():
                continue
            try:
                text = _read_text(md_file)
            except Exception:
                continue

            # Check for substantial NSEC content copy (more than just a reference)
            # Count occurrences of NSEC-specific phrases
            nsec_phrases = [
                "NEXARA Sovereign Engineering Constitution",
                "Fixed Engineering Mainline",
                "Maximum Reachable Endpoint",
                "Complete Delivery Responsibility",
                "Multi-Agent Single Writer",
                "Reality First Override",
                "Article I — Fixed Engineering Mainline",
                "Article II — Maximum Reachable Endpoint",
            ]
            match_count = sum(1 for phrase in nsec_phrases if phrase in text)
            if match_count >= 3:
                issues.append(
                    f"Possible NSEC copy drift in '{md_file.relative_to(REPO_ROOT)}': "
                    f"{match_count} NSEC-specific phrases found. "
                    f"NSEC content must not be duplicated — reference the canonical source instead."
                )

    return issues


# ── Report ────────────────────────────────────────────────────────────────────


def report(issues: list[str]) -> None:
    """Print validation report."""
    print("=" * 60)
    print("  NEXARA PRIME — NSEC Governance Integrity Report")
    print("=" * 60)
    print()
    print(f"  Canonical NSEC: {NSEC_CANONICAL.relative_to(REPO_ROOT)}")
    if NSEC_CANONICAL.exists():
        print(f"  NSEC SHA256:    {_compute_sha256(NSEC_CANONICAL)[:16]}...")
    print()

    if not issues:
        print("  RESULT: NSEC GOVERNANCE INTEGRITY — PASS")
        print("  All NSEC integrity checks passed.")
        print()
        return

    print(f"  RESULT: NSEC GOVERNANCE INTEGRITY — FAIL ({len(issues)} violation(s))")
    print()
    for idx, issue in enumerate(issues, 1):
        print(f"  {idx}. [{_severity(issue)}] {issue}")
    print()


def _severity(issue: str) -> str:
    """Classify issue severity."""
    if "not found" in issue.lower() or "missing" in issue.lower():
        return "CRITICAL"
    if "mismatch" in issue.lower() or "does not" in issue.lower():
        return "HIGH"
    if "copy drift" in issue.lower() or "duplicate" in issue.lower():
        return "HIGH"
    return "MEDIUM"


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> int:
    all_issues: list[str] = []

    # Run all checks
    all_issues.extend(check_canonical_exists())
    all_issues.extend(check_machine_declaration())
    all_issues.extend(check_authority_index())
    all_issues.extend(check_program_constitution_subordination())
    all_issues.extend(check_onepass_skill_binding())
    all_issues.extend(check_agent_bindings())
    all_issues.extend(check_no_duplicate_supreme_authority())
    all_issues.extend(check_ci_binding())
    all_issues.extend(check_broken_references())
    all_issues.extend(check_copy_drift())

    report(all_issues)
    return 0 if not all_issues else 1


if __name__ == "__main__":
    sys.exit(main())
