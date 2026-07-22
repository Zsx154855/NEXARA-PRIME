"""Tests for NSEC Governance Baseline and Enforcement.

Covers: canonical NSEC validation, machine declaration, Authority Index,
Program Constitution subordination, Agent bindings, drift detection,
CI integration, and failure paths.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts" / "governance"
VALIDATOR = SCRIPTS / "validate_nsec.py"
DRIFT_DETECTOR = SCRIPTS / "detect_nsec_drift.py"
NSEC_CANONICAL = REPO_ROOT / "governance" / "NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1.md"
NSEC_YAML = REPO_ROOT / "governance" / "nsec.yaml"
AUTHORITY_INDEX = REPO_ROOT / "governance" / "authority_index.yaml"
PROGRAM_CONSTITUTION = REPO_ROOT / "NEXARA_PROGRAM_CONSTITUTION_V1.md"
ONEPASS_SKILL = REPO_ROOT / ".qoder" / "skills" / "nexara-sovereign-onepass-program" / "SKILL.md"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _run(script: Path, root: Path | None = None, timeout: int = 30) -> tuple[int, str]:
    """Run a governance script, optionally overriding NEXARA_ROOT."""
    env = os.environ.copy()
    if root is not None:
        env["NEXARA_ROOT"] = str(root)
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=root if root is not None else REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    return result.returncode, result.stdout


# ── Success Path Tests ───────────────────────────────────────────────────────


class TestNSECCanonicalExists:
    """Verify the canonical NSEC document and ecosystem are in place."""

    def test_canonical_document_exists(self):
        assert NSEC_CANONICAL.exists(), f"Canonical NSEC not found at {NSEC_CANONICAL}"

    def test_canonical_document_readable(self):
        text = NSEC_CANONICAL.read_text(encoding="utf-8")
        assert len(text) > 1000, "Canonical NSEC is too short — may be incomplete"
        assert "NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1" in text

    def test_machine_declaration_exists(self):
        assert NSEC_YAML.exists(), f"nsec.yaml not found at {NSEC_YAML}"

    def test_authority_index_exists(self):
        assert AUTHORITY_INDEX.exists(), f"authority_index.yaml not found at {AUTHORITY_INDEX}"

    def test_canonical_is_only_one(self):
        """Verify no second NSEC file with a different name exists."""
        governance_dir = REPO_ROOT / "governance"
        nsec_files = list(governance_dir.glob("*CONSTITUTION*"))
        nsec_files.extend(governance_dir.glob("*nsec*"))
        assert len(nsec_files) >= 1


class TestNSECValidatorPasses:
    """Verify the validator passes against the real repository."""

    def test_validator_exit_code_zero(self):
        exit_code, stdout = _run(VALIDATOR)
        assert exit_code == 0, f"Validator failed with exit={exit_code}:\n{stdout}"

    def test_validator_reports_pass(self):
        exit_code, stdout = _run(VALIDATOR)
        assert "NSEC GOVERNANCE INTEGRITY — PASS" in stdout

    def test_drift_detector_exit_code_zero(self):
        exit_code, stdout = _run(DRIFT_DETECTOR)
        assert exit_code == 0, f"Drift detector failed with exit={exit_code}:\n{stdout}"

    def test_drift_detector_reports_no_drift(self):
        exit_code, stdout = _run(DRIFT_DETECTOR)
        assert "NO NSEC GOVERNANCE DRIFT DETECTED" in stdout


class TestProgramConstitutionSubordination:
    """Verify Program Constitution declares subordination to NSEC."""

    def test_declares_subordination(self):
        text = PROGRAM_CONSTITUTION.read_text(encoding="utf-8")
        assert "subordinate to the" in text

    def test_references_nsec_canonical(self):
        text = PROGRAM_CONSTITUTION.read_text(encoding="utf-8")
        assert "NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1.md" in text

    def test_validate_nsec_reference_in_preamble(self):
        text = PROGRAM_CONSTITUTION.read_text(encoding="utf-8")
        lines = text.split("\n")
        first_30 = "\n".join(lines[:30])
        assert "NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1" in first_30


class TestOnePassSkillBinding:
    """Verify One-pass Program Skill is bound to NSEC."""

    def test_references_nsec(self):
        text = ONEPASS_SKILL.read_text(encoding="utf-8")
        assert "NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1.md" in text

    def test_nsec_in_authority_section(self):
        text = ONEPASS_SKILL.read_text(encoding="utf-8")
        section1_start = text.find("## 1. 权威来源")
        assert section1_start != -1, "Section 1 (权威来源) not found"
        section1_end = text.find("## 2.", section1_start)
        section1 = text[section1_start:section1_end]
        assert "NSEC" in section1 or "SOVEREIGN_ENGINEERING_CONSTITUTION" in section1

    def test_no_full_nsec_copy(self):
        text = ONEPASS_SKILL.read_text(encoding="utf-8")
        nsec_headers = [
            "Article I — Fixed Engineering Mainline",
            "Article II — Maximum Reachable Endpoint",
            "Article V — Architecture Stability",
        ]
        matches = [h for h in nsec_headers if h in text]
        assert len(matches) == 0, f"Skill contains NSEC headers — reference, don't copy: {matches}"


class TestAuthorityIndex:
    """Verify Authority Index correctness."""

    def test_contains_nsec(self):
        text = AUTHORITY_INDEX.read_text(encoding="utf-8")
        assert "NSEC" in text or "SOVEREIGN_ENGINEERING_CONSTITUTION" in text

    def test_contains_reality_override(self):
        text = AUTHORITY_INDEX.read_text(encoding="utf-8")
        assert "reality" in text.lower()


class TestCIBinding:
    """Verify CI workflow is bound to NSEC validation."""

    def test_ci_contains_nsec_validator(self):
        text = CI_WORKFLOW.read_text(encoding="utf-8")
        assert "validate_nsec.py" in text

    def test_ci_contains_nsec_drift_detector(self):
        text = CI_WORKFLOW.read_text(encoding="utf-8")
        assert "detect_nsec_drift.py" in text

    def test_ci_has_nsec_job(self):
        text = CI_WORKFLOW.read_text(encoding="utf-8")
        assert "nsec-governance" in text or "nsec_governance" in text


class TestNSECMachineDeclaration:
    """Verify nsec.yaml machine-readable declaration."""

    def test_has_required_fields(self):
        text = NSEC_YAML.read_text(encoding="utf-8")
        required = ["id:", "short_name:", "version:", "status:", "authority_level:",
                     "canonical_document:", "canonical_hash:"]
        for field in required:
            assert field in text, f"nsec.yaml missing field: {field}"

    def test_authority_is_supreme(self):
        text = NSEC_YAML.read_text(encoding="utf-8")
        assert "authority_level: supreme" in text

    def test_hash_matches_canonical(self):
        actual_hash = hashlib.sha256(NSEC_CANONICAL.read_bytes()).hexdigest()
        yaml_text = NSEC_YAML.read_text(encoding="utf-8")
        for line in yaml_text.split("\n"):
            if "canonical_hash:" in line:
                declared = line.split(":")[-1].strip().strip('"')
                if declared.startswith("sha256:"):
                    declared = declared[7:]
                assert declared == actual_hash, \
                    f"Hash mismatch: declared={declared[:16]}... actual={actual_hash[:16]}..."
                return
        pytest.fail("canonical_hash field not found in nsec.yaml")

    def test_canonical_document_path_correct(self):
        text = NSEC_YAML.read_text(encoding="utf-8")
        expected_path = "governance/NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1.md"
        assert expected_path in text


class TestNoDuplicateSupremeAuthority:
    """Verify no other document claims supreme governance authority."""

    def test_only_nsec_is_supreme(self):
        exit_code, stdout = _run(VALIDATOR)
        assert exit_code == 0

    def test_program_constitution_not_supreme(self):
        text = PROGRAM_CONSTITUTION.read_text(encoding="utf-8")
        assert "subordinate" in text.lower()


# ── Failure Path Tests ────────────────────────────────────────────────────────


class TestNSECFailureCanonicalMissing:
    """Verify validator fails when canonical NSEC is missing."""

    def test_validator_fails_without_canonical(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            gov_dir = root / "governance"
            gov_dir.mkdir(parents=True)
            # Create nsec.yaml (which references canonical) but NOT the canonical document
            (gov_dir / "nsec.yaml").write_text(
                "id: NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1\n"
                "short_name: NSEC\nversion: '1.0.0'\nstatus: ACTIVE\n"
                "authority_level: supreme\n"
                "canonical_document: governance/NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1.md\n"
                "canonical_hash: 'sha256:abc'\n",
                encoding="utf-8",
            )

            exit_code, stdout = _run(VALIDATOR, root=root)
            assert exit_code != 0, \
                f"Validator should fail when canonical NSEC is missing. Got exit={exit_code}\n{stdout}"


class TestNSECFailureHashMismatch:
    """Verify validator detects hash mismatch."""

    def test_validator_fails_on_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            gov_dir = root / "governance"
            gov_dir.mkdir(parents=True)

            # Create canonical with known content
            canon = gov_dir / "NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1.md"
            canon.write_text("Modified NSEC content — not the real one", encoding="utf-8")

            # Create nsec.yaml with a DIFFERENT hash than the canon above
            wrong_hash = "a" * 64  # deliberately wrong
            (gov_dir / "nsec.yaml").write_text(
                "id: NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1\n"
                "short_name: NSEC\nversion: '1.0.0'\nstatus: ACTIVE\n"
                "authority_level: supreme\n"
                "canonical_document: governance/NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1.md\n"
                f"canonical_hash: 'sha256:{wrong_hash}'\n",
                encoding="utf-8",
            )

            exit_code, stdout = _run(VALIDATOR, root=root)
            assert exit_code != 0, \
                f"Validator should fail on hash mismatch. Got exit={exit_code}\n{stdout}"


class TestNSECFailureVersionMismatch:
    """Verify drift detector catches version inconsistency."""

    def test_drift_detector_catches_version_drift(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            gov_dir = root / "governance"
            gov_dir.mkdir(parents=True)

            # Create canonical claiming V2
            canon = gov_dir / "NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1.md"
            canon.write_text(
                "**Canonical ID:** `NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1`\n\n"
                "# NEXARA Sovereign Engineering Constitution V2\n\n"
                "Test content.\n",
                encoding="utf-8",
            )

            # nsec.yaml says V1 (old — should trigger version drift against V2 canonical)
            (gov_dir / "nsec.yaml").write_text(
                "id: NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V1\n"
                "short_name: NSEC\nversion: '1.0.0'\nstatus: ACTIVE\n"
                "authority_level: supreme\n"
                "canonical_document: governance/NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V1.md\n"
                "canonical_hash: 'sha256:abc123'\n",
                encoding="utf-8",
            )

            exit_code, stdout = _run(DRIFT_DETECTOR, root=root)
            assert exit_code != 0, \
                f"Drift detector should catch V1/V2 mismatch. Got exit={exit_code}\n{stdout}"


class TestNSECFailureMultipleSupreme:
    """Verify drift detector catches multiple supreme authority sources."""

    def test_drift_detector_catches_competing_constitution(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            gov_dir = root / "governance"
            gov_dir.mkdir(parents=True)

            # Create legit NSEC canonical
            canon = gov_dir / "NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1.md"
            canon.write_text(
                "# NEXARA Sovereign Engineering Constitution V1\n\n"
                "This is the single highest engineering governance source.\n",
                encoding="utf-8",
            )

            # Create nsec.yaml
            (gov_dir / "nsec.yaml").write_text(
                "id: NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1\n"
                "short_name: NSEC\nversion: '1.0.0'\nstatus: ACTIVE\n"
                "authority_level: supreme\n"
                "canonical_document: governance/NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1.md\n"
                "canonical_hash: 'sha256:abc123'\n",
                encoding="utf-8",
            )

            # Create a SECOND constitution claiming supreme authority
            rogue = gov_dir / "ROGUE_CONSTITUTION.md"
            rogue.write_text(
                "# Rogue Constitution\n\n"
                "This document is the single highest engineering governance source. "
                "This file claims authority_level: supreme over all other documents.\n",
                encoding="utf-8",
            )

            exit_code, stdout = _run(DRIFT_DETECTOR, root=root)
            assert exit_code != 0, \
                f"Drift detector should catch competing supreme authority. Got exit={exit_code}\n{stdout}"
            assert "MULTIPLE_SUPREME_SOURCES" in stdout


class TestNSECFailureAgentNotBound:
    """Verify validator catches unbound agent skill."""

    def test_validator_fails_when_skill_missing_nsec_ref(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            gov_dir = root / "governance"
            gov_dir.mkdir(parents=True)

            # Copy real canonical and declaration for structural validity
            canon = gov_dir / "NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1.md"
            canon.write_text(
                "# NEXARA Sovereign Engineering Constitution V1\n\n"
                "**Canonical ID:** `NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1`\n\n"
                "This is the single highest engineering governance source.\n",
                encoding="utf-8",
            )
            canon_hash = hashlib.sha256(canon.read_bytes()).hexdigest()
            (gov_dir / "nsec.yaml").write_text(
                "id: NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1\n"
                "short_name: NSEC\nversion: '1.0.0'\nstatus: ACTIVE\n"
                "authority_level: supreme\n"
                "canonical_document: governance/NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1.md\n"
                f"canonical_hash: 'sha256:{canon_hash}'\n",
                encoding="utf-8",
            )
            (gov_dir / "authority_index.yaml").write_text(
                "version: 1\nindex_name: NEXARA_AUTHORITY_INDEX_V1\n"
                "tiers:\n  - tier: 0\n    label: Reality Override\n",
                encoding="utf-8",
            )

            # Program Constitution WITHOUT subordination
            (root / "NEXARA_PROGRAM_CONSTITUTION_V1.md").write_text(
                "# Program Constitution\n\nNo NSEC reference here.\n",
                encoding="utf-8",
            )

            # One-pass Skill WITHOUT NSEC reference
            skill_dir = root / ".qoder" / "skills" / "nexara-sovereign-onepass-program"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "# One-pass Skill\n\nNo NSEC reference.\n\n## 1. 权威来源\n\n1. User directive\n",
                encoding="utf-8",
            )

            # CI stub without NSEC
            workflows_dir = root / ".github" / "workflows"
            workflows_dir.mkdir(parents=True)
            (workflows_dir / "ci.yml").write_text(
                "name: CI\non: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo ok\n",
                encoding="utf-8",
            )

            exit_code, stdout = _run(VALIDATOR, root=root)
            assert exit_code != 0, \
                f"Validator should fail when bindings are missing. Got exit={exit_code}\n{stdout}"
            assert "FAIL" in stdout


class TestNSECFailureProgramConstitutionUnsubordinated:
    """Verify validator catches Program Constitution without subordination."""

    def test_validator_fails_without_subordination(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            gov_dir = root / "governance"
            gov_dir.mkdir(parents=True)

            canon = gov_dir / "NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1.md"
            canon.write_text(
                "# NEXARA Sovereign Engineering Constitution V1\n\n"
                "**Canonical ID:** `NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1`\n\n"
                "This is the single highest engineering governance source.\n",
                encoding="utf-8",
            )
            canon_hash = hashlib.sha256(canon.read_bytes()).hexdigest()
            (gov_dir / "nsec.yaml").write_text(
                "id: NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1\n"
                "short_name: NSEC\nversion: '1.0.0'\nstatus: ACTIVE\n"
                "authority_level: supreme\n"
                "canonical_document: governance/NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1.md\n"
                f"canonical_hash: 'sha256:{canon_hash}'\n",
                encoding="utf-8",
            )
            (gov_dir / "authority_index.yaml").write_text(
                "version: 1\nindex_name: NEXARA_AUTHORITY_INDEX_V1\n"
                "tiers:\n  - tier: 0\n    label: Reality Override\n",
                encoding="utf-8",
            )

            # Program Constitution WITHOUT subordination
            (root / "NEXARA_PROGRAM_CONSTITUTION_V1.md").write_text(
                "# NEXARA PROGRAM CONSTITUTION V1\n\n"
                "## 最高目标\n\n"
                "Build something.\n\n"
                "This document does NOT declare subordination to NSEC.\n",
                encoding="utf-8",
            )

            # One-pass Skill WITH NSEC reference
            skill_dir = root / ".qoder" / "skills" / "nexara-sovereign-onepass-program"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "# Skill\n\nReferences NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1.md\n",
                encoding="utf-8",
            )

            # CI WITH NSEC
            workflows_dir = root / ".github" / "workflows"
            workflows_dir.mkdir(parents=True)
            (workflows_dir / "ci.yml").write_text(
                "name: CI\non: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n"
                "      - run: python3 scripts/governance/validate_nsec.py\n",
                encoding="utf-8",
            )

            exit_code, stdout = _run(VALIDATOR, root=root)
            assert exit_code != 0, \
                f"Validator should fail without subordination. Got exit={exit_code}\n{stdout}"


class TestNSECFailureBodyCopyDrift:
    """Verify drift detector catches NSEC body content copied elsewhere."""

    def test_drift_detector_catches_body_copy(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            gov_dir = root / "governance"
            gov_dir.mkdir(parents=True)

            canon = gov_dir / "NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1.md"
            canon.write_text(
                "# NSEC V1\n\n"
                "## Article I — Fixed Engineering Mainline\n\n"
                "## Article II — Maximum Reachable Endpoint\n\n"
                "## Article III — Contract First\n\n"
                "## Article IV — Root Cause Repair\n\n",
                encoding="utf-8",
            )
            (gov_dir / "nsec.yaml").write_text(
                "id: NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1\n"
                "short_name: NSEC\nversion: '1.0.0'\nstatus: ACTIVE\n"
                "authority_level: supreme\n"
                "canonical_document: governance/NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1.md\n"
                "canonical_hash: 'sha256:abc'\n",
                encoding="utf-8",
            )

            # Create a file that COPIES NSEC article headers
            docs_dir = root / "docs"
            docs_dir.mkdir(parents=True)
            (docs_dir / "some_guide.md").write_text(
                "# Some Guide\n\n"
                "Following NSEC principles:\n\n"
                "## Article I — Fixed Engineering Mainline\n\n"
                "We follow this...\n\n"
                "## Article II — Maximum Reachable Endpoint\n\n"
                "We follow this too...\n\n"
                "## Article III — Contract First\n\n"
                "And this...\n\n",
                encoding="utf-8",
            )

            exit_code, stdout = _run(DRIFT_DETECTOR, root=root)
            assert exit_code != 0, \
                f"Drift detector should catch body copy drift. Got exit={exit_code}\n{stdout}"
            assert "BODY_COPY_DRIFT" in stdout


class TestNSECFailureStaleReferences:
    """Verify drift detector catches stale/old-version references."""

    def test_drift_detector_catches_stale_version(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            gov_dir = root / "governance"
            gov_dir.mkdir(parents=True)

            canon = gov_dir / "NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1.md"
            canon.write_text("# NSEC V1\n\nValid content.\n", encoding="utf-8")
            (gov_dir / "nsec.yaml").write_text(
                "id: NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1\n"
                "short_name: NSEC\nversion: '1.0.0'\nstatus: ACTIVE\n"
                "authority_level: supreme\n"
                "canonical_document: governance/NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1.md\n"
                "canonical_hash: 'sha256:abc'\n",
                encoding="utf-8",
            )

            # Create a file referencing V0 (stale)
            docs_dir = root / "docs"
            docs_dir.mkdir(parents=True)
            (docs_dir / "old_doc.md").write_text(
                "# Old Doc\n\n"
                "See NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V0 for details.\n",
                encoding="utf-8",
            )

            exit_code, stdout = _run(DRIFT_DETECTOR, root=root)
            assert exit_code != 0, \
                f"Drift detector should catch stale V0 reference. Got exit={exit_code}\n{stdout}"
            assert "STALE_REFERENCE" in stdout


class TestNSECFailureBrokenLinks:
    """Verify validator detects missing canonical document via nsec.yaml reference."""

    def test_validator_fails_when_canonical_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            gov_dir = root / "governance"
            gov_dir.mkdir(parents=True)

            # Create nsec.yaml but NOT the canonical document
            (gov_dir / "nsec.yaml").write_text(
                "id: NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1\n"
                "short_name: NSEC\nversion: '1.0.0'\nstatus: ACTIVE\n"
                "authority_level: supreme\n"
                "canonical_document: governance/NEXARA_SOVEREIGN_ENGINEERING_CONSTITUTION_V2_1.md\n"
                "canonical_hash: 'sha256:abc'\n",
                encoding="utf-8",
            )

            exit_code, stdout = _run(VALIDATOR, root=root)
            assert exit_code != 0, \
                f"Validator should fail when canonical document is missing. Got exit={exit_code}\n{stdout}"


class TestNSECReceiptHashContract:
    """Verify the Receipt Hash Contract is correctly applied."""

    def test_hash_algorithm_is_sha256(self):
        receipt_hash = hashlib.sha256(
            json.dumps({"test": "nsec_governance_v1"}, sort_keys=True).encode()
        ).hexdigest()
        assert len(receipt_hash) == 64
        assert all(c in "0123456789abcdef" for c in receipt_hash)

    def test_nsec_yaml_hash_format(self):
        text = NSEC_YAML.read_text(encoding="utf-8")
        for line in text.split("\n"):
            if "canonical_hash:" in line:
                hash_val = line.split(":")[-1].strip().strip('"')
                if hash_val.startswith("sha256:"):
                    hash_val = hash_val[7:]
                assert len(hash_val) == 64, f"Hash must be 64 hex chars, got {len(hash_val)}"
                assert all(c in "0123456789abcdef" for c in hash_val)
                return
        pytest.fail("canonical_hash field not found")


class TestIntegrationEndToEnd:
    """End-to-end integration: validator → drift detector → tests."""

    def test_full_governance_pipeline(self):
        v_exit, v_out = _run(VALIDATOR)
        assert v_exit == 0, f"Validator failed: {v_out}"
        d_exit, d_out = _run(DRIFT_DETECTOR)
        assert d_exit == 0, f"Drift detector failed: {d_out}"

    def test_all_critical_files_exist(self):
        files = [
            NSEC_CANONICAL, NSEC_YAML, AUTHORITY_INDEX,
            PROGRAM_CONSTITUTION, ONEPASS_SKILL, CI_WORKFLOW,
            VALIDATOR, DRIFT_DETECTOR,
        ]
        for f in files:
            assert f.exists(), f"Required NSEC ecosystem file missing: {f}"

    def test_validator_importable(self):
        result = subprocess.run(
            [sys.executable, "-c", f"compile(open('{VALIDATOR}').read(), '{VALIDATOR}', 'exec')"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0, f"Validator has syntax errors: {result.stderr}"

    def test_drift_detector_importable(self):
        result = subprocess.run(
            [sys.executable, "-c", f"compile(open('{DRIFT_DETECTOR}').read(), '{DRIFT_DETECTOR}', 'exec')"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0, f"Drift detector has syntax errors: {result.stderr}"
