"""NEXARA Sovereign Product Reality Engine foundation.

This package is additive. It does not modify mission execution, approval,
evidence, audit, sandbox, provider, or Adaptive Runtime behavior.
"""

from .evolution import EvolutionPromotionGate
from .genome import ExperienceGenomeRegistry
from .models import (
    DriftFinding,
    DriftType,
    EvolutionProposal,
    EvolutionValidation,
    ExperienceGene,
    ProductSurface,
    ProductTwinCheckpoint,
    PromotionDecision,
    TwinSnapshot,
)
from .twin import ProductTwinEngine

__all__ = [
    "DriftFinding",
    "DriftType",
    "EvolutionPromotionGate",
    "EvolutionProposal",
    "EvolutionValidation",
    "ExperienceGene",
    "ExperienceGenomeRegistry",
    "ProductSurface",
    "ProductTwinCheckpoint",
    "ProductTwinEngine",
    "PromotionDecision",
    "TwinSnapshot",
]
