"""M4 controlled A→B experience transfer experiment (deterministic, local only).

Purpose: measure whether verified experiences from task A change success on an
unseen task B relative to a frozen cold-start policy, and whether revoking the
experiences removes the effect.

Scope limits (must be reported with results):
- synthetic deterministic environment; keyword recall; no LLM/provider calls;
- success means the simulated operation's deterministic outcome, not business value;
- not a substitute for a real Task A→B production experiment.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .brain.db import BrainDB
from .brain.experience_learner import ExperienceLearner
from .brain.memory_controller import MemoryController
from .db import SQLiteStore
from .events import EventBus
from .evidence import EvidenceStore
from .models import ToolInvocation

DEFAULT_ACTION = "claude_adapter"
LEARNED_ACTION = "python_adapter"
TASK_KEYWORDS = "invoice adapter"


@dataclass(frozen=True)
class TransferEpisode:
    episode_id: str
    mission_id: str
    objective: str
    keywords: str = TASK_KEYWORDS


def simulate_action(action: str, *, environment: str = "learned_ok") -> bool:
    """Deterministic environment; ``default_ok`` models a distribution shift."""
    if environment == "default_ok":
        return action == DEFAULT_ACTION
    return action == LEARNED_ACTION


class ExperienceTransferExperiment:
    """Cold-start vs verified-experience policy, with revocation check."""

    def __init__(
        self,
        workdir: Path,
        *,
        training_episodes: int = 6,
        task_b_episodes: int = 6,
        profile: str = "learned_succeeds",
        task_b_environment: str = "learned_ok",
    ) -> None:
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        if profile not in {"learned_succeeds", "default_succeeds"}:
            raise ValueError("unknown_training_profile")
        if task_b_environment not in {"learned_ok", "default_ok"}:
            raise ValueError("unknown_task_b_environment")
        self.training_episodes = training_episodes
        self.task_b_episodes = task_b_episodes
        self.profile = profile
        self.task_b_environment = task_b_environment
        self.brain = BrainDB(self.workdir / "brain.db")
        self.core = SQLiteStore(self.workdir / "core.db")
        self.evidence = EvidenceStore(self.core, EventBus(self.core))
        self.mc = MemoryController(db=self.brain)
        self.learner = ExperienceLearner(self.mc, evidence_store=self.evidence)
        self._training_memory_ids: list[str] = []
        self._success_memory_ids: list[str] = []
        self._ran = False

    # ── setup ──

    def _receipt(self, mission_id: str, action: str, success: bool):
        invocation = ToolInvocation(
            mission_id=mission_id,
            tool_name=action,
            status="completed" if success else "failed",
            result={"ok": success},
            trace_id=f"trace-{mission_id}",
        )
        return self.evidence.add(
            mission_id, "execution_receipt", f"Tool receipt: {action}",
            invocation.model_dump_json(), invocation.trace_id,
            tool_invocation_id=invocation.invocation_id,
            actor="tool_runtime", source="tool_runtime",
            verification_status="verified",
        )

    def record_training(self) -> list[str]:
        """Task A: successes for the profile's winning action, failures for the other."""
        successes = max(self.training_episodes - 2, 1)
        for i in range(self.training_episodes):
            success = i < successes
            if self.profile == "learned_succeeds":
                action = LEARNED_ACTION if success else DEFAULT_ACTION
            else:
                action = DEFAULT_ACTION if success else LEARNED_ACTION
            mission_id = f"task-A-{i}"
            receipt = self._receipt(mission_id, action, success)
            memory_id = self.learner.record_outcome(
                mission_id,
                "success" if success else "failure",
                action,
                "ok" if success else "failed",
                success,
                evidence_id=receipt.evidence_id,
            )
            self._training_memory_ids.append(memory_id)
            if success:
                self._success_memory_ids.append(memory_id)
        return list(self._training_memory_ids)

    def _episodes(self) -> list[TransferEpisode]:
        return [
            TransferEpisode(
                episode_id=f"task-B-{i}",
                mission_id=f"task-B-{i}",
                objective=f"reconcile vendor invoices case {i}",
            )
            for i in range(self.task_b_episodes)
        ]

    # ── policies ──

    def _evaluate(self, episodes: list[TransferEpisode], policy: str) -> dict[str, Any]:
        successes = 0
        influenced = 0
        actions: list[str] = []
        evidence_used: list[str] = []
        for episode in episodes:
            action = DEFAULT_ACTION
            if policy == "experienced":
                decision = self.learner.recommend_action(episode.keywords)
                recommended = decision.get("action")
                if recommended:
                    action = recommended
                    if action != DEFAULT_ACTION:
                        influenced += 1
                    evidence_used.extend(decision.get("evidence_ids", []))
            actions.append(action)
            if simulate_action(action, environment=self.task_b_environment):
                successes += 1
        total = len(episodes)
        return {
            "policy": policy,
            "episodes": total,
            "successes": successes,
            "success_rate": round(successes / max(total, 1), 4),
            "errors": total - successes,
            "tool_calls": total,
            "influenced_decisions": influenced,
            "actions": actions,
            "evidence_ids_used": sorted(set(evidence_used)),
        }

    def revoke(self) -> dict[str, Any]:
        """Retire learned experiences from active recall (lifecycle archive)."""
        revoked = 0
        for memory_id in self._training_memory_ids:
            if self.brain.update_status(memory_id, "archived"):
                revoked += 1
        return {"revoked": revoked, "of": len(self._training_memory_ids)}

    # ── run ──

    def run(self, *, train: bool = True) -> dict[str, Any]:
        if self._ran:
            raise RuntimeError("experiment_already_ran")
        self._ran = True
        if train:
            self.record_training()
        episodes = self._episodes()
        cold = self._evaluate(episodes, "cold_start")
        experienced = self._evaluate(episodes, "experienced")
        revocation = self.revoke() if train else {"revoked": 0, "of": 0}
        revoked = self._evaluate(episodes, "experienced_after_revocation")
        delta = round(experienced["success_rate"] - cold["success_rate"], 4)
        return {
            "config": {
                "training_episodes": self.training_episodes if train else 0,
                "task_b_episodes": self.task_b_episodes,
                "default_action": DEFAULT_ACTION,
                "learned_action": LEARNED_ACTION,
                "profile": self.profile,
                "task_b_environment": self.task_b_environment,
                "seed": 7,
            },
            "training": {
                "episodes": self.training_episodes if train else 0,
                "successes": len(self._success_memory_ids) if train else 0,
                "failures": (self.training_episodes - len(self._success_memory_ids)) if train else 0,
                "profile": self.profile,
            },
            "cold_start": cold,
            "experienced": experienced,
            "delta_success_rate": delta,
            "revocation": revocation,
            "after_revocation": revoked,
            "revocation_effective": (
                revoked["success_rate"] == cold["success_rate"]
                and revoked["influenced_decisions"] == 0
            ),
            "cost": {"model_calls": 0, "network_calls": 0, "local_tool_calls": cold["tool_calls"] + experienced["tool_calls"] + revoked["tool_calls"]},
            "limits": (
                "Synthetic deterministic benchmark; keyword recall; no provider calls. "
                "Success measures the simulated environment outcome, not business value."
            ),
        }

    def close(self) -> None:
        self.brain.close()
        self.core.close() if hasattr(self.core, "close") else None


def run_experiment(workdir: Path, *, train: bool = True) -> dict[str, Any]:
    experiment = ExperienceTransferExperiment(workdir)
    try:
        return experiment.run(train=train)
    finally:
        experiment.close()


def write_result(result: dict[str, Any], path: Path) -> None:
    Path(path).write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
