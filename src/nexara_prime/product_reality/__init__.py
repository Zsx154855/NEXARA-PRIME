"""NEXARA Sovereign Product Reality Engine V2 foundation.

This package is additive. It does not modify mission execution, ApprovalEngine,
EvidenceStore, audit, sandbox, provider, secret, or Adaptive Runtime behavior.
"""

from .evolution import EvolutionPromotionGate
from .genome import ExperienceGenomeRegistry
from .models import (
    DriftFinding,
    DriftType,
    DriftValue,
    EvolutionProposal,
    EvolutionValidation,
    ExperienceGene,
    ProductSurface,
    ProductTwinCheckpoint,
    PromotionDecision,
    TwinSnapshot,
    ValuePresence,
)
from .twin import ProductTwinEngine

__all__ = [
    "DriftFinding",
    "DriftType",
    "DriftValue",
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
    "ValuePresence",
]
