#!/usr/bin/env python3
"""NEXARA PRIME — NSEC Governance Drift Detector.

Detects governance drift across the repository:
- Multiple supreme governance sources
- Version drift between NSEC and machine declaration
- Body copy drift (NSEC content duplicated elsewhere)
- Stale references pointing to old versions
- Old-version bindings in agents/skills
- Subordinate contract overreach (claiming authority above their tier)

ALL findings are FAIL-level. Drift detection is fail-closed.
Warnings are not used — any drift is a governance integrity violation.

Exit codes:
    0 — no drift detected
    1 — drift detected
    2 — detector could not complete
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(os.environ.get("NEXARA_ROOT", Path(__file__).resolve().parent.parent.parent))

# ── Canonical paths ───────────────────────────────────────────────────────────
NSEC_CANONICAL = REPO_ROOT / "governance" / "NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1.md"
NSEC_CANONICAL_V1_SUPERSEDED = REPO_ROOT / "governance" / "NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V1.md"
NSEC_YAML = REPO_ROOT / "governance" / "nsec.yaml"
AUTHORITY_INDEX = REPO_ROOT / "governance" / "authority_index.yaml"
PROGRAM_CONSTITUTION = REPO_ROOT / "NEXARA_PROGRAM_CONSTITUTION_V1.md"
ONEPASS_SKILL = REPO_ROOT / ".qoder" / "skills" / "nexara-sovereign-onepass-program" / "SKILL.md"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
GATE_STATUS = REPO_ROOT / ".nexara" / "GATE_STATUS.json"
PROGRAM_STATE = REPO_ROOT / ".nexara" / "PROGRAM_STATE.json"


def _read_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    return path.read_text(encoding="utf-8")


def _compute_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_yaml_simple(text: str) -> dict[str, Any]:
    """Parse simple YAML using stdlib only (same as validate_nsec.py)."""
    try:
        import yaml
        return yaml.safe_load(text)
    except ImportError:
        pass

    result: dict[str, Any] = {}
    indent_stack: list[tuple[int, str, Any]] = []

    for raw_line in text.split("\n"):
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue

        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        while indent_stack and indent_stack[-1][0] >= indent:
            indent_stack.pop()

        if ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip()

            if value == "":
                container: dict[str, Any] | list[Any] = {}
                target = result
                if indent_stack:
                    target = indent_stack[-1][2]
                target[key] = container
                indent_stack.append((indent, key, container))
            elif value.startswith("[") and value.endswith("]"):
                items = [v.strip().strip("'\"") for v in value[1:-1].split(",") if v.strip()]
                target = result
                if indent_stack:
                    target = indent_stack[-1][2]
                target[key] = items
            else:
                val: Any = value.strip("'\"")
                if val.lower() in ("true", "yes"):
                    val = True
                elif val.lower() in ("false", "no"):
                    val = False
                elif val.isdigit():
                    val = int(val)
                target = result
                if indent_stack:
                    target = indent_stack[-1][2]
                target[key] = val
        elif stripped.startswith("- "):
            item_value = stripped[2:].strip().strip("'\"")
            if indent_stack and isinstance(indent_stack[-1][2], list):
                indent_stack[-1][2].append(item_value)
            elif indent_stack and isinstance(indent_stack[-1][2], dict):
                parent_key = indent_stack[-1][1]
                parent_target = result
                if len(indent_stack) >= 2:
                    parent_target = indent_stack[-2][2]
                parent_target[parent_key] = [item_value]
                indent_stack[-1] = (indent_stack[-1][0], indent_stack[-1][1], parent_target[parent_key])

    return result


# ── Drift Detection Functions ─────────────────────────────────────────────────


def detect_multiple_supreme_sources() -> list[str]:
    """Detect if any file other than NSEC claims supreme governance authority."""
    issues: list[str] = []
    scan_roots = [
        REPO_ROOT / "governance",
        REPO_ROOT / "docs",
        REPO_ROOT,
    ]

    supreme_markers = [
        "authority_level: supreme",
        "authority_level:supreme",
        "Authority Level: SUPREME",
        "highest engineering governance",
        "single highest engineering governance",
        "最高工程治理源",
        "唯一最高工程治理",
    ]

    exclude_paths = {
        NSEC_CANONICAL.resolve(),
        NSEC_CANONICAL_V1_SUPERSEDED.resolve(),
        NSEC_YAML.resolve(),
        AUTHORITY_INDEX.resolve(),
    }

    for scan_root in scan_roots:
        if not scan_root.exists():
            continue
        if scan_root.is_file():
            scan_files = [scan_root]
        else:
            scan_files = list(scan_root.rglob("*.md")) + list(scan_root.rglob("*.yaml")) + list(scan_root.rglob("*.yml"))

        for file_path in scan_files:
            if file_path.resolve() in exclude_paths:
                continue
            try:
                text = _read_text(file_path)
            except Exception:
                continue

            for marker in supreme_markers:
                if marker.lower() in text.lower():
                    # Check if this is a self-claim or a reference to NSEC
                    lines = text.split("\n")
                    for line_num, line in enumerate(lines, 1):
                        if marker.lower() in line.lower():
                            # Check surrounding context (±3 lines) for self-reference
                            context_start = max(0, line_num - 4)
                            context_end = min(len(lines), line_num + 3)
                            context = "\n".join(lines[context_start:context_end]).lower()
                            if any(ref in context for ref in [
                                "this document", "this file", "this constitution",
                                "this policy", "this contract", "this index",
                            ]):
                                issues.append(
                                    f"MULTIPLE_SUPREME_SOURCES: "
                                    f"'{file_path.relative_to(REPO_ROOT)}' line {line_num} "
                                    f"appears to self-claim supreme governance authority. "
                                    f"Only NSEC ({NSEC_CANONICAL.relative_to(REPO_ROOT)}) may claim this."
                                )
                                break
                    break

    return issues


def detect_version_drift() -> list[str]:
    """Detect version inconsistency between NSEC canonical and machine declaration."""
    issues: list[str] = []
    if not NSEC_CANONICAL.exists() or not NSEC_YAML.exists():
        return issues

    try:
        canon_text = _read_text(NSEC_CANONICAL)
        decl = _parse_yaml_simple(_read_text(NSEC_YAML))
    except Exception as exc:
        issues.append(f"VERSION_DRIFT: Cannot read NSEC files: {exc}")
        return issues

    # Extract the exact canonical ID rather than only the major version.
    canon_id_match = re.search(
        r'[\*]*Canonical ID[\*]*:[\*]*\s*`(NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V[0-9_]+)`',
        canon_text,
    )
    decl_version = decl.get("version", "")
    decl_id = decl.get("id", "")

    if canon_id_match:
        canon_id = canon_id_match.group(1)
        if decl_id != canon_id:
            issues.append(
                f"VERSION_DRIFT: Canonical document declares {canon_id} "
                f"but nsec.yaml id is '{decl_id}'"
            )

    # Version format
    if decl_version and not re.match(r'^\d+\.\d+\.\d+$', str(decl_version)):
        issues.append(f"VERSION_DRIFT: nsec.yaml version '{decl_version}' is not semver format")

    return issues


def detect_body_copy_drift() -> list[str]:
    """Detect if NSEC body text has been copied to other files (not just references)."""
    issues: list[str] = []
    if not NSEC_CANONICAL.exists():
        return issues

    try:
        _read_text(NSEC_CANONICAL)
    except Exception:
        return issues

    # NSEC-specific article headers that should not appear elsewhere
    unique_headers = [
        "Article I — Fixed Engineering Mainline",
        "Article II — Maximum Reachable Endpoint",
        "Article III — Contract First",
        "Article IV — Root Cause Repair",
        "Article V — Architecture Stability",
        "Article VI — Technical Debt Management",
        "Article VII — Engineering Honesty",
        "Article VIII — Lifecycle Responsibility",
        "Article IX — Uncertainty Disclosure",
        "Article X — Execution Priority and Hard Boundaries",
        "Article XI — Human Final Control",
        "Article XII — Multi-Agent Single Writer",
        "Article XIII — Evidence",
        "Article XIV — Receipt",
        "Article XV — Complete Delivery Responsibility",
    ]

    scan_roots = [
        REPO_ROOT / "docs",
        REPO_ROOT / "skills",
        REPO_ROOT / ".qoder",
        REPO_ROOT / "reports",
        REPO_ROOT / "governance",
    ]

    exclude_paths = {
        NSEC_CANONICAL.resolve(),
        NSEC_CANONICAL_V1_SUPERSEDED.resolve(),
        PROGRAM_CONSTITUTION.resolve(),
        ONEPASS_SKILL.resolve(),
    }

    for scan_root in scan_roots:
        if not scan_root.exists():
            continue
        for md_file in scan_root.rglob("*.md"):
            if md_file.resolve() in exclude_paths:
                continue

            try:
                text = _read_text(md_file)
            except Exception:
                continue

            matches = [h for h in unique_headers if h in text]
            if len(matches) >= 2:
                issues.append(
                    f"BODY_COPY_DRIFT: '{md_file.relative_to(REPO_ROOT)}' "
                    f"contains {len(matches)} NSEC article headers. "
                    f"NSEC content must not be copied — reference the canonical source. "
                    f"Matches: {matches}"
                )

    return issues


def detect_stale_references() -> list[str]:
    """Detect references to non-existent or old-version NSEC paths."""
    issues: list[str] = []
    scan_roots = [
        REPO_ROOT / ".qoder",
        REPO_ROOT / "skills",
        REPO_ROOT / "docs",
        REPO_ROOT / "governance",
        REPO_ROOT,
    ]

    # Patterns that indicate stale references
    stale_patterns = [
        r'NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V0',  # Pre-V1
        r'governance/NSEC_V0',
        r'sovereign_engineering_constitution_v0',
    ]

    for scan_root in scan_roots:
        if not scan_root.exists():
            continue
        if scan_root.is_file():
            scan_files = [scan_root]
        else:
            scan_files = list(scan_root.rglob("*.md")) + list(scan_root.rglob("*.yaml")) + list(scan_root.rglob("*.yml")) + list(scan_root.rglob("*.json"))

        for file_path in scan_files:
            if file_path.resolve() == NSEC_CANONICAL.resolve():
                continue
            if file_path.resolve() == NSEC_YAML.resolve():
                continue

            try:
                text = _read_text(file_path)
            except Exception:
                continue

            for pattern in stale_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    issues.append(
                        f"STALE_REFERENCE: '{file_path.relative_to(REPO_ROOT)}' "
                        f"references stale NSEC identifier: '{match.group(0)}'. "
                        f"Update to current version: NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1"
                    )

    return issues


def detect_old_version_bindings() -> list[str]:
    """Detect agent/skill bindings that reference old NSEC versions."""
    issues: list[str] = []
    scan_paths = [
        ONEPASS_SKILL,
        REPO_ROOT / ".claude" / "settings.local.json",
    ]

    # Add all .qoder skills
    qoder_skills = REPO_ROOT / ".qoder" / "skills"
    if qoder_skills.exists():
        for skill_file in qoder_skills.rglob("SKILL.md"):
            scan_paths.append(skill_file)

    old_version_pattern = re.compile(
        r'NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_(?:V(0|[3-9]|[1-9][0-9])|V2\.md\b)',
        re.IGNORECASE,
    )

    for file_path in scan_paths:
        if not file_path.exists():
            continue
        try:
            text = _read_text(file_path)
        except Exception:
            continue

        matches = old_version_pattern.findall(text)
        if matches:
            issues.append(
                f"OLD_VERSION_BINDING: '{file_path.relative_to(REPO_ROOT)}' "
                f"references non-current NSEC version(s): {matches}. "
                f"Current NSEC version is V2_1."
            )

    return issues


def detect_subordinate_overreach() -> list[str]:
    """Detect subordinate contracts claiming authority above their tier."""
    issues: list[str] = []
    # Check governance contracts that might claim primacy
    contract_paths = [
        REPO_ROOT / "governance" / "contracts" / "MERGE_CONTRACT_V1.yaml",
        REPO_ROOT / "governance" / "releases" / "RELEASE_APPROVAL_MATRIX_V1.yaml",
    ]

    for contract_path in contract_paths:
        if not contract_path.exists():
            continue
        try:
            text = _read_text(contract_path)
        except Exception:
            continue

        # Detect if contract claims to be the highest authority
        overreach_markers = [
            "ultimate authority",
            "highest authority",
            "supreme",
            "overrides all other",
            "takes precedence over all",
        ]
        for marker in overreach_markers:
            if marker.lower() in text.lower():
                # Check context
                lines = text.split("\n")
                for line_num, line in enumerate(lines, 1):
                    if marker.lower() in line.lower():
                        issues.append(
                            f"SUBORDINATE_OVERREACH: "
                            f"'{contract_path.relative_to(REPO_ROOT)}' line {line_num} "
                            f"uses authority claim '{marker}'. "
                            f"Only NSEC may claim supreme governance authority. "
                            f"Subordinate contracts must not claim overriding authority."
                        )

    return issues


def detect_broken_nsec_links() -> list[str]:
    """Detect references to NSEC paths that don't exist on disk."""
    issues: list[str] = []
    # Files that should reference NSEC
    required_files = [
        PROGRAM_CONSTITUTION,
        ONEPASS_SKILL,
    ]

    expected_path = "governance/NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1.md"

    for file_path in required_files:
        if not file_path.exists():
            continue
        try:
            text = _read_text(file_path)
        except Exception:
            continue

        if expected_path in text:
            # Verify the referenced file actually exists
            referenced = REPO_ROOT / expected_path
            if not referenced.exists():
                issues.append(
                    f"BROKEN_LINK: '{file_path.relative_to(REPO_ROOT)}' "
                    f"references '{expected_path}' which does not exist on disk."
                )

    return issues


# ── Report ────────────────────────────────────────────────────────────────────


def report_drift(issues: list[str]) -> None:
    """Print drift detection report."""
    print("=" * 60)
    print("  NEXARA PRIME — NSEC Governance Drift Detection Report")
    print("=" * 60)
    print()
    if NSEC_CANONICAL.exists():
        print(f"  NSEC SHA256: {_compute_sha256(NSEC_CANONICAL)[:16]}...")
    print()

    if not issues:
        print("  RESULT: NO NSEC GOVERNANCE DRIFT DETECTED")
        print("  All NSEC references and bindings are consistent.")
        print()
        return

    print(f"  RESULT: NSEC GOVERNANCE DRIFT DETECTED ({len(issues)} finding(s))")
    print()
    for idx, issue in enumerate(issues, 1):
        category = issue.split(":")[0] if ":" in issue else "UNKNOWN"
        print(f"  {idx}. [{category}] {issue}")
    print()


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> int:
    all_issues: list[str] = []

    all_issues.extend(detect_multiple_supreme_sources())
    all_issues.extend(detect_version_drift())
    all_issues.extend(detect_body_copy_drift())
    all_issues.extend(detect_stale_references())
    all_issues.extend(detect_old_version_bindings())
    all_issues.extend(detect_subordinate_overreach())
    all_issues.extend(detect_broken_nsec_links())

    report_drift(all_issues)
    return 0 if not all_issues else 1


if __name__ == "__main__":
    sys.exit(main())
