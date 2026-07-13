from __future__ import annotations

import re
from enum import Enum

from pydantic import Field, field_validator, model_validator

from nexara_prime.models import NModel, RiskLevel


IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]*$")
SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?$")


def _identifier(value: str) -> str:
    normalized = value.strip()
    if not IDENTIFIER.fullmatch(normalized):
        raise ValueError("identifier_must_be_lower_snake_case")
    return normalized


def _unique(values: list[str], label: str) -> list[str]:
    if len(values) != len(set(values)):
        raise ValueError(f"duplicate_{label}")
    return values


class OutputTarget(str, Enum):
    PYTHON = "python"
    TESTS = "tests"
    DOCS = "docs"
    OPENAPI = "openapi"
    ARCHITECTURE = "architecture"
    SWIFT = "swift"
    DESIGN_OS = "design_os"
    EVIDENCE = "evidence"


class EnforcementPhase(str, Enum):
    COMPILE = "compile"
    VALIDATE = "validate"
    RUNTIME = "runtime"
    RELEASE = "release"


class TestKind(str, Enum):
    HAPPY = "happy"
    NEGATIVE = "negative"
    BOUNDARY = "boundary"
    REPLAY = "replay"
    MUTATION = "mutation"
    ROLLBACK = "rollback"


class SystemIdentity(NModel):
    id: str
    name: str = Field(min_length=1)
    version: str
    owner: str = Field(min_length=1)

    _normalize_id = field_validator("id")(_identifier)

    @field_validator("name", "owner")
    @classmethod
    def non_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value_must_not_be_blank")
        return normalized

    @field_validator("version")
    @classmethod
    def semantic_version(cls, value: str) -> str:
        normalized = value.strip()
        if not SEMVER.fullmatch(normalized):
            raise ValueError("version_must_be_semver")
        return normalized


class ConstitutionSpec(NModel):
    mission_first: bool = True
    evidence_required: bool = True
    reversible_by_default: bool = True
    human_authority_preserved: bool = True
    deterministic_builds: bool = True

    @model_validator(mode="after")
    def sovereign_baseline_cannot_be_disabled(self) -> "ConstitutionSpec":
        disabled = [
            name
            for name in (
                "mission_first",
                "evidence_required",
                "reversible_by_default",
                "human_authority_preserved",
                "deterministic_builds",
            )
            if not getattr(self, name)
        ]
        if disabled:
            raise ValueError("sovereign_constitution_disabled:" + ",".join(disabled))
        return self


class FieldSpec(NModel):
    name: str
    type: str = Field(min_length=1)
    required: bool = True
    description: str = Field(min_length=1)

    _normalize_name = field_validator("name")(_identifier)

    @field_validator("type", "description")
    @classmethod
    def non_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value_must_not_be_blank")
        return normalized


class EntitySpec(NModel):
    id: str
    description: str = Field(min_length=1)
    fields: list[FieldSpec] = Field(min_length=1)

    _normalize_id = field_validator("id")(_identifier)

    @model_validator(mode="after")
    def unique_fields(self) -> "EntitySpec":
        _unique([field.name for field in self.fields], "field_id")
        return self


class PolicyRuleSpec(NModel):
    id: str
    description: str = Field(min_length=1)
    assertion: str = Field(min_length=1)
    failure_code: str
    enforcement_phase: EnforcementPhase
    risk_tiers: list[RiskLevel] = Field(min_length=1)
    test_ids: list[str] = Field(min_length=1)

    _normalize_id = field_validator("id", "failure_code")(_identifier)

    @field_validator("test_ids")
    @classmethod
    def normalize_test_ids(cls, values: list[str]) -> list[str]:
        return _unique([_identifier(value) for value in values], "policy_test_id")

    @model_validator(mode="after")
    def unique_risk_tiers(self) -> "PolicyRuleSpec":
        _unique([tier.value for tier in self.risk_tiers], "risk_tier")
        return self


class GeneratedTestSpec(NModel):
    id: str
    rule_id: str
    kind: TestKind
    description: str = Field(min_length=1)

    _normalize_ids = field_validator("id", "rule_id")(_identifier)


class DomainSpec(NModel):
    entities: list[EntitySpec] = Field(min_length=1)
    dependencies: list[str] = Field(default_factory=list)

    @field_validator("dependencies")
    @classmethod
    def normalize_dependencies(cls, values: list[str]) -> list[str]:
        return _unique([_identifier(value) for value in values], "dependency")

    @model_validator(mode="after")
    def unique_entities(self) -> "DomainSpec":
        _unique([entity.id for entity in self.entities], "entity_id")
        return self


class SovereignSystemIR(NModel):
    schema_version: str = "1.0.0"
    system: SystemIdentity
    constitution: ConstitutionSpec
    domain: DomainSpec
    policies: list[PolicyRuleSpec] = Field(min_length=1)
    tests: list[GeneratedTestSpec] = Field(min_length=1)
    outputs: list[OutputTarget] = Field(min_length=1)

    @field_validator("schema_version")
    @classmethod
    def supported_schema(cls, value: str) -> str:
        if value != "1.0.0":
            raise ValueError("unsupported_ssc_schema_version")
        return value

    @model_validator(mode="after")
    def validate_graph(self) -> "SovereignSystemIR":
        policy_ids = _unique([policy.id for policy in self.policies], "policy_id")
        test_ids = _unique([test.id for test in self.tests], "test_id")
        _unique([target.value for target in self.outputs], "output_target")

        if self.system.id in self.domain.dependencies:
            raise ValueError("system_cannot_depend_on_itself")

        policies = set(policy_ids)
        tests = set(test_ids)
        bound_by_rule: dict[str, set[str]] = {policy_id: set() for policy_id in policy_ids}
        for test in self.tests:
            if test.rule_id not in policies:
                raise ValueError(f"test_references_unknown_policy:{test.id}")
            bound_by_rule[test.rule_id].add(test.id)

        for policy in self.policies:
            declared = set(policy.test_ids)
            missing = declared - tests
            if missing:
                raise ValueError(f"policy_references_unknown_test:{policy.id}:{sorted(missing)[0]}")
            if declared != bound_by_rule[policy.id]:
                raise ValueError(f"policy_test_binding_mismatch:{policy.id}")

        kinds = {test.kind for test in self.tests}
        if TestKind.NEGATIVE not in kinds:
            raise ValueError("negative_test_required")
        if TestKind.ROLLBACK not in kinds:
            raise ValueError("rollback_test_required")
        if OutputTarget.EVIDENCE not in self.outputs:
            raise ValueError("evidence_output_required")
        return self


class BuildArtifact(NModel):
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)


class BuildManifest(NModel):
    manifest_version: str = "1.0.0"
    compiler_version: str
    system_id: str
    system_version: str
    ir_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    build_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifacts: list[BuildArtifact]

