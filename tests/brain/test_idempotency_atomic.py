"""DB-IDEMPOTENCY-ATOMIC-01: multi-process duplicate experience/receipt protection.

Real SQLite, real subprocesses. Two processes record the same mission + receipt
concurrently; exactly one experience and one evidence row may exist, and both
processes must return the same memory id. Also covers replay, payload conflict,
legacy rows and an orphaned claim left by a crash.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "src"
SDK = REPO / "platform" / "sdk" / "python"

CHILD = textwrap.dedent(
    """
    import json
    import os
    import sys
    import time
    from pathlib import Path

    root = Path(sys.argv[1])
    mission_id = sys.argv[2]
    evidence_id = sys.argv[3]
    action = sys.argv[4]
    result = sys.argv[5]
    success = sys.argv[6] == "1"
    ready = Path(sys.argv[7])
    out = Path(sys.argv[8])

    from nexara_prime.brain.db import BrainDB
    from nexara_prime.brain.experience_learner import ExperienceLearner
    from nexara_prime.brain.memory_controller import MemoryController
    from nexara_prime.db import SQLiteStore
    from nexara_prime.events import EventBus
    from nexara_prime.evidence import EvidenceStore

    brain = BrainDB(root / "brain.db")
    core = SQLiteStore(root / "core.db")
    evidence = EvidenceStore(core, EventBus(core))
    learner = ExperienceLearner(MemoryController(db=brain), evidence_store=evidence)

    ready.write_text("1")
    go = root / "go"
    deadline = time.time() + 30
    while not go.exists():
        if time.time() > deadline:
            sys.exit(3)
        time.sleep(0.005)

    memory_id = learner.record_outcome(
        mission_id, "success" if success else "failure", action,
        result, success, evidence_id=evidence_id,
    )
    out.write_text(memory_id)
    """
)


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(SRC), str(SDK), env.get("PYTHONPATH", "")])
    return env


def _make_fixture(tmp_path: Path):
    from nexara_prime.brain.db import BrainDB
    from nexara_prime.brain.memory_controller import MemoryController
    from nexara_prime.db import SQLiteStore
    from nexara_prime.events import EventBus
    from nexara_prime.evidence import EvidenceStore
    from nexara_prime.models import ToolInvocation

    brain = BrainDB(tmp_path / "brain.db")
    core = SQLiteStore(tmp_path / "core.db")
    evidence = EvidenceStore(core, EventBus(core))
    controller = MemoryController(db=brain)
    invocation = ToolInvocation(
        mission_id="mission-A", tool_name="run_pytest", status="completed",
        result={"ok": True, "n": 1}, trace_id="trace-A",
    )
    artifact = evidence.add(
        "mission-A", "execution_receipt", "Tool receipt: run_pytest",
        invocation.model_dump_json(), invocation.trace_id,
        tool_invocation_id=invocation.invocation_id,
        actor="tool_runtime", source="tool_runtime", verification_status="verified",
    )
    return brain, core, controller, artifact


def _open(tmp_path: Path):
    from nexara_prime.brain.db import BrainDB
    from nexara_prime.brain.memory_controller import MemoryController
    from nexara_prime.db import SQLiteStore

    brain = BrainDB(tmp_path / "brain.db")
    core = SQLiteStore(tmp_path / "core.db")
    return brain, core, MemoryController(db=brain)


def _run_children(tmp_path: Path, n: int, evidence_id: str, result: str = "ok"):
    script = tmp_path / "child.py"
    script.write_text(CHILD, encoding="utf-8")
    procs = []
    outs = []
    for i in range(n):
        ready = tmp_path / f"ready-{i}"
        out = tmp_path / f"out-{i}"
        outs.append(out)
        procs.append(
            subprocess.Popen(
                [sys.executable, str(script), str(tmp_path), "mission-A",
                 evidence_id, "run_pytest", result, "1", str(ready), str(out)],
                env=_env(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
        )
    deadline = time.time() + 30
    while not all((tmp_path / f"ready-{i}").exists() for i in range(n)):
        if time.time() > deadline:
            for proc in procs:
                proc.kill()
            raise AssertionError("children did not become ready")
        time.sleep(0.01)
    (tmp_path / "go").write_text("1")
    results = []
    for proc in procs:
        stdout, stderr = proc.communicate(timeout=60)
        assert proc.returncode == 0, (stderr or stdout)
        results.append(stdout)
    return [out.read_text() for out in outs]


def _counts(brain, core) -> tuple[int, int]:
    with brain._lock:
        experiences = brain._conn.execute(
            "SELECT COUNT(*) FROM brain_memories WHERE kind='experience'"
        ).fetchone()[0]
    return experiences, len(core.list_records("evidence"))


def test_two_processes_record_one_experience(tmp_path):
    brain, core, controller, artifact = _make_fixture(tmp_path)
    brain.close()
    core.close()

    ids = _run_children(tmp_path, 2, artifact.evidence_id)
    assert len(set(ids)) == 1

    brain, core, controller = _open(tmp_path)
    try:
        assert _counts(brain, core) == (1, 1)
    finally:
        brain.close()
        core.close()


def test_replay_after_restart_returns_same_memory(tmp_path):
    brain, core, controller, artifact = _make_fixture(tmp_path)
    brain.close()
    core.close()

    first = _run_children(tmp_path, 1, artifact.evidence_id)[0]
    (tmp_path / "go").unlink()
    second = _run_children(tmp_path, 1, artifact.evidence_id)[0]
    assert first == second

    brain, core, controller = _open(tmp_path)
    try:
        assert _counts(brain, core) == (1, 1)
    finally:
        brain.close()
        core.close()


def test_payload_conflict_is_rejected_without_duplicate(tmp_path):
    brain, core, controller, artifact = _make_fixture(tmp_path)
    brain.close()
    core.close()

    _run_children(tmp_path, 1, artifact.evidence_id, result="ok")
    (tmp_path / "go").unlink()
    (tmp_path / "go").write_text("1")
    script = tmp_path / "child.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path), "mission-A",
         artifact.evidence_id, "run_pytest", "different", "1",
         str(tmp_path / "ready-x"), str(tmp_path / "out-x")],
        env=_env(), capture_output=True, text=True, timeout=60,
    )
    assert result.returncode != 0
    assert "idempotency_conflict" in result.stderr

    brain, core, controller = _open(tmp_path)
    try:
        assert _counts(brain, core) == (1, 1)
    finally:
        brain.close()
        core.close()


def test_orphaned_claim_from_crash_is_recovered(tmp_path):
    brain, core, controller, artifact = _make_fixture(tmp_path)
    key = f"exp:mission-A:{artifact.evidence_id}"
    payload_sha = __import__("hashlib").sha256(
        json.dumps(
            {
                "mission_id": "mission-A", "key": key, "kind": "experience",
                "evidence_id": artifact.evidence_id, "action": "run_pytest",
                "outcome": "success", "result": "ok", "success": True,
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    claimed, _, _ = brain.claim_idempotency(
        "mission-A", key, "mem-orphan", payload_sha
    )
    assert claimed is True
    brain.close()
    core.close()

    ids = _run_children(tmp_path, 1, artifact.evidence_id)
    assert ids[0] and ids[0] != "mem-orphan"

    brain, core, controller = _open(tmp_path)
    try:
        assert _counts(brain, core) == (1, 1)
    finally:
        brain.close()
        core.close()


def test_legacy_row_is_reused_instead_of_duplicated(tmp_path):
    brain, core, controller, artifact = _make_fixture(tmp_path)
    content = json.dumps({
        "mission_id": "mission-A", "outcome": "success", "action": "run_pytest",
        "result": "ok", "success": True, "evidence_id": artifact.evidence_id,
    })
    legacy_id = controller.commit(
        mission_id="mission-A", key="exp:mission-A:legacy-random",
        content=content, kind="experience", evidence_id=artifact.evidence_id,
        confidence=0.5,
    )
    brain.close()
    core.close()

    ids = _run_children(tmp_path, 1, artifact.evidence_id)
    assert ids[0] == legacy_id

    brain, core, controller = _open(tmp_path)
    try:
        assert _counts(brain, core) == (1, 1)
    finally:
        brain.close()
        core.close()


def test_claim_and_memory_insert_are_one_transaction(tmp_path):
    brain, core, controller = _open(tmp_path)
    try:
        existing = {
            "memory_id": "mem-existing", "mission_id": "mission-A",
            "key": "exp:existing", "content": "{}", "kind": "experience",
            "layer": "semantic", "created_at": "2026-01-01T00:00:00+00:00",
        }
        brain.insert_memory(existing)
        conflicting = dict(existing, key="exp:new")
        try:
            brain.insert_memory_with_idempotency(
                conflicting, "mission-A", "exp:new", "sha-new"
            )
        except Exception:
            pass
        else:
            raise AssertionError("duplicate memory_id must fail")
        with brain._lock:
            claim = brain._conn.execute(
                "SELECT 1 FROM brain_memory_idempotency WHERE mem_key='exp:new'"
            ).fetchone()
        assert claim is None
    finally:
        brain.close()
        core.close()
