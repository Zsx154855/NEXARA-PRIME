from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from nexara_prime.cli import main
from nexara_prime.ssc import SSCCompiler, SovereignSystemIR, load_ir


def _payload() -> dict:
    return {
        "schema_version": "1.0.0",
        "system": {"id": "product_reality", "name": "Product Reality", "version": "2.0.0", "owner": "NEXARA"},
        "constitution": {
            "mission_first": True,
            "evidence_required": True,
            "reversible_by_default": True,
            "human_authority_preserved": True,
            "deterministic_builds": True,
        },
        "domain": {
            "entities": [
                {
                    "id": "evolution_proposal",
                    "description": "A governed product evolution candidate.",
                    "fields": [
                        {"name": "proposal_id", "type": "string", "required": True, "description": "Stable proposal identity."}
                    ],
                }
            ],
            "dependencies": ["evidence", "approval"],
        },
        "policies": [
            {
                "id": "promotion_evidence",
                "description": "Every promotion requires verified mission-bound evidence.",
                "assertion": "evidence.exists and evidence.verified and evidence.same_mission",
                "failure_code": "promotion_evidence_required",
                "enforcement_phase": "runtime",
                "risk_tiers": ["R0", "R1", "R2", "R3", "R4"],
                "test_ids": ["promotion_evidence_missing", "promotion_evidence_ok", "promotion_rollback_ok"],
            }
        ],
        "tests": [
            {"id": "promotion_evidence_missing", "rule_id": "promotion_evidence", "kind": "negative", "description": "Reject absent evidence."},
            {"id": "promotion_evidence_ok", "rule_id": "promotion_evidence", "kind": "happy", "description": "Accept verified evidence."},
            {"id": "promotion_rollback_ok", "rule_id": "promotion_evidence", "kind": "rollback", "description": "Preserve rollback path."},
        ],
        "outputs": ["python", "tests", "docs", "architecture", "evidence"],
    }


def _ir() -> SovereignSystemIR:
    return SovereignSystemIR.model_validate(_payload())


def test_compilation_is_byte_for_byte_deterministic(tmp_path: Path) -> None:
    compiler = SSCCompiler()
    first = compiler.compile(_ir(), tmp_path / "first")
    second = compiler.compile(_ir(), tmp_path / "second")
    assert first == second
    first_files = {path.relative_to(tmp_path / "first"): path.read_bytes() for path in (tmp_path / "first").rglob("*") if path.is_file()}
    second_files = {path.relative_to(tmp_path / "second"): path.read_bytes() for path in (tmp_path / "second").rglob("*") if path.is_file()}
    assert first_files == second_files


def test_manifest_binds_every_non_manifest_artifact(tmp_path: Path) -> None:
    manifest = SSCCompiler().compile(_ir(), tmp_path / "out")
    assert manifest.system_id == "product_reality"
    assert [item.path for item in manifest.artifacts] == sorted(item.path for item in manifest.artifacts)
    assert "build-manifest.json" not in {item.path for item in manifest.artifacts}
    assert len(manifest.build_sha256) == 64


def test_compile_refuses_nonempty_output(tmp_path: Path) -> None:
    output = tmp_path / "out"
    output.mkdir()
    (output / "owned.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(ValueError, match="ssc_output_not_empty"):
        SSCCompiler().compile(_ir(), output)
    assert (output / "owned.txt").read_text(encoding="utf-8") == "keep"


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda p: p["constitution"].update({"evidence_required": False}), "sovereign_constitution_disabled"),
        (lambda p: p["domain"].update({"dependencies": ["product_reality"]}), "system_cannot_depend_on_itself"),
        (lambda p: p.update({"outputs": ["python", "tests"]}), "evidence_output_required"),
        (lambda p: p["tests"].__setitem__(0, {**p["tests"][0], "rule_id": "missing_rule"}), "test_references_unknown_policy"),
        (lambda p: p["policies"][0].update({"test_ids": ["promotion_evidence_ok"]}), "policy_test_binding_mismatch"),
        (lambda p: p.update({"tests": [test for test in p["tests"] if test["kind"] != "negative"]}) or p["policies"][0].update({"test_ids": ["promotion_evidence_ok", "promotion_rollback_ok"]}), "negative_test_required"),
        (lambda p: p["system"].update({"id": "../escape"}), "identifier_must_be_lower_snake_case"),
        (lambda p: p["system"].update({"version": "v2"}), "version_must_be_semver"),
    ],
)
def test_invalid_ir_fails_closed(mutate, message: str) -> None:
    payload = _payload()
    mutate(payload)
    with pytest.raises(ValidationError, match=message):
        SovereignSystemIR.model_validate(payload)


def test_duplicate_json_keys_are_rejected(tmp_path: Path) -> None:
    source = tmp_path / "duplicate.json"
    source.write_text('{"schema_version":"1.0.0","schema_version":"1.0.0"}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate_json_key"):
        load_ir(source)


def test_unknown_fields_are_rejected() -> None:
    payload = _payload()
    payload["unexpected"] = True
    with pytest.raises(ValidationError, match="extra_forbidden"):
        SovereignSystemIR.model_validate(payload)


def test_cli_validates_and_compiles_without_starting_runtime(tmp_path: Path, capsys) -> None:
    source = tmp_path / "system.json"
    source.write_text(json.dumps(_payload()), encoding="utf-8")
    assert main(["ssc", "validate", str(source)]) == 0
    validated = json.loads(capsys.readouterr().out)
    assert validated["valid"] is True
    assert main(["ssc", "compile", str(source), "--output", str(tmp_path / "build")]) == 0
    compiled = json.loads(capsys.readouterr().out)
    assert compiled["system_id"] == "product_reality"
    assert (tmp_path / "build" / "build-manifest.json").is_file()
