from __future__ import annotations

from pathlib import Path

from .models import MissionSpec, RiskLevel


class MissionCompiler:
    """Deterministic MVP compiler; a model gateway can replace its parser later."""

    def compile(self, objective: str, source_dir: str | None = None) -> MissionSpec:
        objective = objective.strip()
        if not objective:
            raise ValueError("objective_must_not_be_empty")
        lowered = objective.lower()
        risk = RiskLevel.R2
        if any(word in lowered for word in ("delete", "deploy", "payment", "pay", "send externally", "生产")):
            risk = RiskLevel.R3
        elif any(word in lowered for word in ("report", "write", "generate", "生成", "报告")):
            risk = RiskLevel.R2
        elif any(word in lowered for word in ("read", "inspect", "analy", "summarize", "读取", "分析")):
            risk = RiskLevel.R1
        title = objective.split("\n", 1)[0][:90]
        files = []
        if source_dir:
            root = Path(source_dir).expanduser().resolve()
            if not root.exists() or not root.is_dir():
                raise ValueError(f"source_dir_not_found:{root}")
            for path in sorted(root.rglob("*")):
                if path.is_file() and len(files) < 100:
                    files.append(f"{path.relative_to(root)} ({path.stat().st_size} bytes)")
        boundaries = ["Only operate inside the explicitly approved local workspace.", "Do not contact external systems.", "Do not delete or overwrite source materials."]
        constraints = ["Use deterministic mock model when no provider is configured.", "Keep a trace and evidence artifact for every state change.", "Respect Writer Lease before report writes."]
        deliverables = ["MissionSpec", "WorkContract", "execution plan", "verified local report", "evidence bundle", "Memory Patch"]
        if files:
            constraints.append(f"Source inventory captured for {len(files)} local files.")
        return MissionSpec(
            title=title,
            objective=objective,
            boundaries=boundaries,
            constraints=constraints,
            deliverables=deliverables,
            risks=["bounded local write requires human approval", "source evidence may be incomplete"],
            acceptance_criteria=["full state machine trace exists", "report is written only after approval", "verification and evidence are present", "evaluation passes safety and evidence gates"],
            risk_level=risk,
            source_dir=str(Path(source_dir).expanduser().resolve()) if source_dir else None,
        )
