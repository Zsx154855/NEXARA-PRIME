"""Shared pytest fixtures for Phase 2B brain tests."""
import pytest

_LAYER_MAP = {"preference": "semantic", "experience": "episodic", "procedural": "procedural"}


class MockMC:
    """Mock MemoryController matching real API: commit, recall, rank_retrieve."""

    def __init__(self):
        self.store: dict[str, list[dict]] = {}

    def commit(self, *a, **kw):
        mission_id = kw.get("mission_id", a[0] if a else "")
        key = kw.get("key", a[1] if len(a) > 1 else "")
        content = kw.get("content", a[2] if len(a) > 2 else "")
        kind = kw.get("kind", a[3] if len(a) > 3 else "")
        evidence_id = kw.get("evidence_id", a[4] if len(a) > 4 else None)
        confidence = kw.get("confidence", a[5] if len(a) > 5 else 1.0)
        self.store.setdefault(mission_id, []).append({
            "mission_id": mission_id, "key": key, "content": content,
            "kind": kind, "layer": _LAYER_MAP.get(kind, kind),
            "evidence_id": evidence_id or "", "confidence": confidence,
            "status": "active", "weight": confidence,
        })
        return f"cid_{len(self.store.get(mission_id, []))}"

    def recall(self, mission_id, layer=None, **kw):
        res = []
        for mid, recs in self.store.items():
            if mission_id != "global" and mid != mission_id:
                continue
            for r in recs:
                if r["status"] != "active":
                    continue
                if layer is not None and r.get("layer") != layer:
                    continue
                res.append(r)
        return res

    def rank_retrieve(self, query, top_k=10, layers=None, min_confidence=0.3, **kw):
        res = []
        for recs in self.store.values():
            for r in recs:
                if r["status"] != "active":
                    continue
                if layers and r.get("layer") not in layers:
                    continue
                if float(r.get("confidence", 1)) < min_confidence:
                    continue
                if any(w.lower() in str(r).lower() for w in query.lower().split()):
                    res.append(r)
        return res[:top_k]


@pytest.fixture
def mock_mc():
    return MockMC()
