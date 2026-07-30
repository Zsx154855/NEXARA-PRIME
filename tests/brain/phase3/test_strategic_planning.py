"""Tests: Strategic Planning Engine."""
import pytest
from src.nexara_prime.brain.strategic_planning import StrategicPlanningEngine

_LAYER = {"preference":"semantic","experience":"episodic","procedural":"procedural"}

class MockMC:
    def __init__(s):
        s.store = {}

    def commit(s, *a, **kw):
        mid = kw.get('mission_id', a[0] if a else '')
        key = kw.get('key', a[1] if len(a) > 1 else '')
        content = kw.get('content', a[2] if len(a) > 2 else '')
        kind = kw.get('kind', a[3] if len(a) > 3 else '')
        s.store.setdefault(mid,[]).append({'mission_id':mid,'key':key,'content':content,'kind':kind,'layer':_LAYER.get(kind,kind),'evidence_id':'','confidence':1.0,'status':'active','weight':1.0})
        return 'ok'
    def recall(s,mid,layer=None,**kw):
        res=[]
        for m,recs in s.store.items():
            if mid!='global' and m!=mid:
                continue
            for r in recs:
                if r['status']!='active':
                    continue
                if layer is not None and r.get('layer')!=layer:
                    continue
                res.append(r)
        return res

@pytest.fixture
def mc(): return MockMC()
@pytest.fixture
def engine(mc): return StrategicPlanningEngine(mc)

class TestPlanning:
    def test_create_plan(self, engine):
        p = engine.create_plan("build feature X")
        assert p.owner_goal == "build feature X"
        assert p.status == "DRAFT"
    def test_generate_strategies(self, engine):
        p = engine.create_plan("goal")
        strategies = engine.generate_strategy_options(p)
        assert len(strategies) >= 2
    def test_decompose_strategy(self, engine):
        p = engine.create_plan("goal")
        strategy = {"name":"phased"}
        missions = engine.decompose_strategy(p, strategy)
        assert len(missions) >= 1
        assert missions[0]["dependencies"] == [] or missions[0]["dependencies"] is not None
    def test_dependency_graph(self, engine):
        missions = [{"id":"m1","dependencies":[]},{"id":"m2","dependencies":["m1"]}]
        deps = engine.build_dependency_graph(missions)
        assert len(deps) == 1
    def test_critical_path(self, engine):
        missions = [{"id":"m1"},{"id":"m2"}]
        path = engine.identify_critical_path(missions)
        assert len(path) == 2
    def test_detect_drift(self, engine):
        p = engine.create_plan("goal")
        assert engine.detect_plan_drift(p, {"status":"PAUSED"})
    def test_no_drift_active(self, engine):
        p = engine.create_plan("goal")
        assert not engine.detect_plan_drift(p, {"status":"ACTIVE"})
    def test_replan(self, engine):
        p = engine.create_plan("goal")
        rp = engine.propose_replan(p)
        assert rp.status == "REPLANNING"
    def test_record_plan(self, engine, mc):
        p = engine.create_plan("goal")
        cid = engine.record_plan(p)
        assert cid is not None
    def test_summarize(self, engine, mc):
        p = engine.create_plan("goal")
        engine.record_plan(p)
        s = engine.summarize()
        assert s["total_plans"] >= 1
