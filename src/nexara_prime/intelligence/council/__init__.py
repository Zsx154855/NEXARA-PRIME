"""V1.2 Intelligence Layer — Agent Council (multi-role collaboration + governance)."""
from .contracts import CouncilAgent, CouncilRole
from .council import AgentCouncil

__all__ = ["CouncilRole", "CouncilAgent", "AgentCouncil"]
