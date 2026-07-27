"""Reasoning Kernel — cognitive inference layer for NEXARA Brain.

Sub-modules:
- kernel: ReasoningKernel + ThoughtProcessEngine
- context_assembler: ContextAssembler + MemoryRetrievalAdapter
- decision_framework: DecisionFramework
- confidence: ConfidenceEngine
- self_check: SelfCheckValidator
- models: ReasoningStep, ReasoningTrace, ReasoningResult, etc.
"""

from .kernel import ReasoningKernel, ThoughtProcessEngine
from .context_assembler import ContextAssembler, MemoryRetrievalAdapter
from .decision_framework import DecisionFramework
from .confidence import ConfidenceEngine, WEIGHTS
from .self_check import SelfCheckValidator
from .models import (
    ReasoningStep, ReasoningTrace, ReasoningResult,
    AssembledContext, MissionContext, Decision, DecisionOption,
    ConfidenceScore, SelfCheckResult,
)

__all__ = [
    "ReasoningKernel", "ThoughtProcessEngine",
    "ContextAssembler", "MemoryRetrievalAdapter",
    "DecisionFramework", "ConfidenceEngine", "WEIGHTS",
    "SelfCheckValidator",
    "ReasoningStep", "ReasoningTrace", "ReasoningResult",
    "AssembledContext", "MissionContext", "Decision",
    "DecisionOption", "ConfidenceScore", "SelfCheckResult",
]
