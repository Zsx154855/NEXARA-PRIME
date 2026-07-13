"""NEXARA Sovereign Product Reality Engine V2 foundation.

The product-reality package is additive. Its governance guarantees rely on
shared ApprovalEngine, EvidenceStore, event-persistence, and SQLite integrity
hardening; mission execution, sandbox, provider, secret, and Adaptive Runtime
behavior remain unchanged.
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
