from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .models import BuildArtifact, BuildManifest, OutputTarget, SovereignSystemIR


COMPILER_VERSION = "1.0.0"
MAX_IR_BYTES = 1_048_576


def canonical_json(value: Any) -> bytes:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate_json_key:{key}")
        result[key] = value
    return result


def load_ir(path: Path | str) -> SovereignSystemIR:
    source = Path(path)
    if not source.is_file():
        raise ValueError(f"ssc_ir_not_found:{source}")
    size = source.stat().st_size
    if size > MAX_IR_BYTES:
        raise ValueError("ssc_ir_too_large")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"), object_pairs_hook=_no_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"ssc_ir_invalid_json:{exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("ssc_ir_root_must_be_object")
    return SovereignSystemIR.model_validate(payload)


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class SSCCompiler:
    """Deterministic, provider-free compiler for Sovereign System IR."""

    def plan(self, ir: SovereignSystemIR) -> dict[str, bytes]:
        canonical_ir = canonical_json(ir)
        files: dict[str, bytes] = {"system.ir.json": canonical_ir}
        outputs = set(ir.outputs)

        if OutputTarget.DOCS in outputs:
            files["README.md"] = self._render_readme(ir).encode("utf-8")
            files["constitution.json"] = canonical_json(ir.constitution)
        if OutputTarget.ARCHITECTURE in outputs:
            files["architecture.json"] = canonical_json(
                {
                    "system": ir.system.id,
                    "dependencies": ir.domain.dependencies,
                    "entities": [entity.id for entity in ir.domain.entities],
                }
            )
        if OutputTarget.PYTHON in outputs:
            files["python/domain_contracts.json"] = canonical_json(
                {"entities": [entity.model_dump(mode="json") for entity in ir.domain.entities]}
            )
            files["python/policies.json"] = canonical_json(
                {"policies": [policy.model_dump(mode="json") for policy in ir.policies]}
            )
        if OutputTarget.TESTS in outputs:
            files["tests/generated_tests.json"] = canonical_json(
                {"tests": [test.model_dump(mode="json") for test in ir.tests]}
            )
        if OutputTarget.OPENAPI in outputs:
            files["openapi/contract.json"] = canonical_json(
                {"openapi": "3.1.0", "info": {"title": ir.system.name, "version": ir.system.version}, "paths": {}}
            )
        if OutputTarget.SWIFT in outputs:
            files["swift/contracts.json"] = canonical_json(
                {"system": ir.system.id, "entities": [entity.id for entity in ir.domain.entities]}
            )
        if OutputTarget.DESIGN_OS in outputs:
            files["design_os/components.json"] = canonical_json(
                {"system": ir.system.id, "projections": []}
            )

        artifacts = [
            BuildArtifact(path=path, sha256=_sha256(content), size_bytes=len(content))
            for path, content in sorted(files.items())
        ]
        build_input = {
            "compiler_version": COMPILER_VERSION,
            "ir_sha256": _sha256(canonical_ir),
            "artifacts": [artifact.model_dump(mode="json") for artifact in artifacts],
        }
        manifest = BuildManifest(
            compiler_version=COMPILER_VERSION,
            system_id=ir.system.id,
            system_version=ir.system.version,
            ir_sha256=build_input["ir_sha256"],
            build_sha256=_sha256(canonical_json(build_input)),
            artifacts=artifacts,
        )
        files["build-manifest.json"] = canonical_json(manifest)
        return dict(sorted(files.items()))

    def compile(self, ir: SovereignSystemIR, output_dir: Path | str) -> BuildManifest:
        destination = Path(output_dir)
        if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
            raise ValueError(f"ssc_output_not_empty:{destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        files = self.plan(ir)

        staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.ssc-", dir=destination.parent))
        try:
            for relative, content in files.items():
                target = staging / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
            if destination.exists():
                destination.rmdir()
            os.replace(staging, destination)
        except Exception:
            for path in sorted(staging.rglob("*"), reverse=True):
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    path.rmdir()
            if staging.exists():
                staging.rmdir()
            raise
        return self.verify(destination)

    def verify(self, output_dir: Path | str) -> BuildManifest:
        """Fail closed unless a build is exactly reproducible by this compiler."""
        root = Path(output_dir)
        if not root.is_dir() or root.is_symlink():
            raise ValueError(f"ssc_build_not_directory:{root}")
        for entry in root.rglob("*"):
            if entry.is_symlink():
                raise ValueError(f"ssc_build_symlink_forbidden:{entry.relative_to(root)}")

        ir = load_ir(root / "system.ir.json")
        expected = self.plan(ir)
        actual_files = {
            path.relative_to(root).as_posix(): path
            for path in root.rglob("*")
            if path.is_file()
        }
        if set(actual_files) != set(expected):
            raise ValueError("ssc_build_artifact_set_mismatch")
        for relative, content in expected.items():
            if actual_files[relative].read_bytes() != content:
                raise ValueError(f"ssc_build_artifact_mismatch:{relative}")

        manifest = BuildManifest.model_validate_json(
            actual_files["build-manifest.json"].read_text(encoding="utf-8")
        )
        if (
            manifest.compiler_version != COMPILER_VERSION
            or manifest.system_id != ir.system.id
            or manifest.system_version != ir.system.version
        ):
            raise ValueError("ssc_build_manifest_identity_mismatch")
        return manifest

    @staticmethod
    def _render_readme(ir: SovereignSystemIR) -> str:
        entities = "\n".join(f"- `{entity.id}` — {entity.description}" for entity in ir.domain.entities)
        policies = "\n".join(f"- `{policy.id}` — {policy.description}" for policy in ir.policies)
        return (
            f"# {ir.system.name}\n\n"
            f"Generated deterministically by NEXARA SSC {COMPILER_VERSION}.\n\n"
            f"System ID: `{ir.system.id}`  \nVersion: `{ir.system.version}`  \nOwner: `{ir.system.owner}`\n\n"
            "## Entities\n\n"
            f"{entities}\n\n"
            "## Policies\n\n"
            f"{policies}\n"
        )
