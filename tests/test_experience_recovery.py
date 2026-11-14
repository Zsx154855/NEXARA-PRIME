"""M3 recovery probe: an experience written before an abrupt process exit survives restart.

The child process commits a verified experience, then calls os._exit(0) without
closing SQLite connections. The parent reopens the same databases in a new
process and must see exactly one experience and one evidence record; a second
child run must add one more, without duplication.

Scope: abnormal-exit-after-commit durability, not a SIGKILL mid-transaction test.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
SDK = REPO / "platform" / "sdk" / "python"

CHILD_SCRIPT = textwrap.dedent(
    """
    import os
    import sys
    from pathlib import Path

    from nexara_prime.brain.db import BrainDB
    from nexara_prime.brain.experience_learner import ExperienceLearner
    from nexara_prime.brain.memory_controller import MemoryController
    from nexara_prime.db import SQLiteStore
    from nexara_prime.events import EventBus
    from nexara_prime.evidence import EvidenceStore
    from nexara_prime.models import ToolInvocation

    root = Path(sys.argv[1])
    mission_id = sys.argv[2]
    brain = BrainDB(root / "brain.db")
    core = SQLiteStore(root / "core.db")
    evidence = EvidenceStore(core, EventBus(core))
    learner = ExperienceLearner(MemoryController(db=brain), evidence_store=evidence)

    invocation = ToolInvocation(
        mission_id=mission_id,
        tool_name="recover_adapter",
        status="completed",
        result={"ok": True},
        trace_id=f"trace-{mission_id}",
    )
    receipt = evidence.add(
        mission_id, "execution_receipt", "Tool receipt: recover_adapter",
        invocation.model_dump_json(), invocation.trace_id,
        tool_invocation_id=invocation.invocation_id,
        actor="tool_runtime", source="tool_runtime",
        verification_status="verified",
    )
    learner.record_outcome(
        mission_id, "success", "recover_adapter", "ok", True,
        evidence_id=receipt.evidence_id,
    )
    os._exit(0)  # abrupt exit: no close(), no atexit()
    """
)


def _child_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(SRC), str(SDK), env.get("PYTHONPATH", "")]
    )
    return env


def _run_child(script: Path, root: Path, mission_id: str) -> None:
    result = subprocess.run(
        [sys.executable, str(script), str(root), mission_id],
        env=_child_env(),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr, result.stderr


def _open(tmp: Path):
    from nexara_prime.brain.db import BrainDB
    from nexara_prime.brain.experience_learner import ExperienceLearner
    from nexara_prime.brain.memory_controller import MemoryController
    from nexara_prime.db import SQLiteStore
    from nexara_prime.events import EventBus
    from nexara_prime.evidence import EvidenceStore

    brain = BrainDB(tmp / "brain.db")
    core = SQLiteStore(tmp / "core.db")
    evidence = EvidenceStore(core, EventBus(core))
    learner = ExperienceLearner(MemoryController(db=brain), evidence_store=evidence)
    return brain, core, evidence, learner


def _counts(brain, core) -> tuple[int, int]:
    with brain._lock:
        memories = brain._conn.execute(
            "SELECT COUNT(*) FROM brain_memories WHERE kind='experience'"
        ).fetchone()[0]
    evidence_records = len(core.list_records("evidence"))
    return memories, evidence_records


def test_experience_survives_abrupt_process_exit(tmp_path):
    script = tmp_path / "child.py"
    script.write_text(CHILD_SCRIPT, encoding="utf-8")

    _run_child(script, tmp_path, "mission-A0")
    brain, core, evidence, learner = _open(tmp_path)
    try:
        assert _counts(brain, core) == (1, 1)
        recalled = learner.rank_experiences("recover_adapter")
        assert len(recalled) == 1
        assert recalled[0].mission_id == "mission-A0"
    finally:
        brain.close()
        core.close()

    _run_child(script, tmp_path, "mission-A1")
    brain, core, evidence, learner = _open(tmp_path)
    try:
        assert _counts(brain, core) == (2, 2)
        missions = {record.mission_id for record in learner.rank_experiences("recover_adapter")}
        assert missions == {"mission-A0", "mission-A1"}
    finally:
        brain.close()
        core.close()
