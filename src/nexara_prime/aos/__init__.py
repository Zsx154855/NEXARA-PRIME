"""NEXARA Autonomous Operating System — execution gateway and supervisor layer.

Builds on the existing RuntimeOrchestrator, adding:
- AutonomousSupervisor: mission planning, dispatch, monitoring
- ExecutionGateway: unified worker adapter registry
- PermissionBroker: risk-based auto-approval (R0-R4)
- RecoveryEngine: multi-strategy auto-recovery
- NotificationGateway: notification routing
- CostOptimizer: token cost tracking + budget enforcement
- ContextCompactor: context compression strategies
"""
from __future__ import annotations

from .supervisor import AutonomousSupervisor, SupervisorConfig
from .execution_gateway import ExecutionGateway, WorkerAdapter
from .permission_broker import PermissionBroker, RiskLevel, PermissionDecision
from .policy_engine import PolicyEngine, PolicyRule, PolicyDecision
from .command_classifier import CommandClassifier, CommandClassification
from .recovery_engine import RecoveryEngine, RecoveryStrategy, RecoveryResult
from .notification_gateway import NotificationGateway, NotificationLevel, Notification
from .cost_optimizer import CostOptimizer, TokenBudget, TokenUsage
from .context_compactor import ContextCompactor, CompactionStrategy
from .runtime_truth_adapter import RuntimeTruthAdapter
from .health_monitor import HealthMonitor, WorkerStatus
from .loop_tool_adapter import LoopToolAdapter

__all__ = [
    "AutonomousSupervisor", "SupervisorConfig",
    "ExecutionGateway", "WorkerAdapter",
    "PermissionBroker", "RiskLevel", "PermissionDecision",
    "PolicyEngine", "PolicyRule", "PolicyDecision",
    "CommandClassifier", "CommandClassification",
    "RecoveryEngine", "RecoveryStrategy", "RecoveryResult",
    "NotificationGateway", "NotificationLevel", "Notification",
    "CostOptimizer", "TokenBudget", "TokenUsage",
    "ContextCompactor", "CompactionStrategy",
    "RuntimeTruthAdapter",
    "HealthMonitor", "WorkerStatus",
    "LoopToolAdapter",
]
