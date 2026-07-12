from __future__ import annotations

from typing import Any

from .models import ExperienceGene, ProductSurface


class ExperienceGenomeRegistry:
    """Version-aware registry for executable experience semantics."""

    def __init__(self) -> None:
        self._genes: dict[str, ExperienceGene] = {}

    def register(self, gene: ExperienceGene) -> None:
        current = self._genes.get(gene.gene_id)
        if current and gene.version <= current.version:
            raise ValueError(
                f"gene {gene.gene_id!r} version must increase "
                f"(current={current.version}, incoming={gene.version})"
            )
        self._genes[gene.gene_id] = gene

    def get(self, gene_id: str) -> ExperienceGene | None:
        return self._genes.get(gene_id)

    def list_all(self) -> list[ExperienceGene]:
        return sorted(self._genes.values(), key=lambda gene: (gene.name, gene.version))

    def resolve(self, context: dict[str, Any]) -> list[ExperienceGene]:
        return [
            gene
            for gene in self.list_all()
            if self._conditions_match(gene.activates_when, context)
        ]

    def validate_projection(
        self,
        gene: ExperienceGene,
        *,
        surface: ProductSurface,
        visible_objects: set[str],
        available_controls: set[str],
    ) -> list[str]:
        errors: list[str] = []

        missing_objects = sorted(set(gene.must_show) - visible_objects)
        if missing_objects:
            errors.append(f"missing required objects: {', '.join(missing_objects)}")

        missing_controls = sorted(set(gene.controls) - available_controls)
        if missing_controls:
            errors.append(f"missing required controls: {', '.join(missing_controls)}")

        prohibited_objects = sorted(set(gene.prohibited) & visible_objects)
        if prohibited_objects:
            errors.append(f"prohibited objects present: {', '.join(prohibited_objects)}")

        if surface.value not in gene.platform_expression:
            errors.append(f"missing platform expression for {surface.value}")

        return errors

    @classmethod
    def _conditions_match(
        cls,
        conditions: dict[str, Any],
        context: dict[str, Any],
    ) -> bool:
        for key, required in conditions.items():
            observed = context.get(key)
            if isinstance(required, list):
                if observed not in required:
                    return False
            elif isinstance(required, dict):
                if not isinstance(observed, dict):
                    return False
                if not cls._conditions_match(required, observed):
                    return False
            elif observed != required:
                return False
        return True
