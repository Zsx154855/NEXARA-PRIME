"""Tests: Deep Reasoning Engine."""
import pytest
from src.nexara_prime.brain.deep_reasoning import DeepReasoningEngine
from src.nexara_prime.brain.cognitive_models import ReasoningDecision

_LAYER = {"preference":"semantic","experience":"episodic","procedural":"procedural"}

class MockMC:
    def __init__(s): s.store = {}
    def commit(s,*a,**kw):
        mid=kw.get('mission_id',a[0]if a else''); key=kw.get('key',a[1]if len(a)>1 else'')
        content=kw.get('content',a[2]if len(a)>2 else''); kind=kw.get('kind',a[3]if len(a)>3 else'')
        ev=kw.get('evidence_id',a[4]if len(a)>4 else None); conf=kw.get('confidence',a[5]if len(a)>5 else 1.0)
        s.store.setdefault(mid,[]).append({'mission_id':mid,'key':key,'content':content,'kind':kind,'layer':_LAYER.get(kind,kind),'evidence_id':ev or '','confidence':conf,'status':'active','weight':conf})
        return 'ok'
    def recall(s,mid,layer=None,**kw):
        res=[]
        for m,recs in s.store.items():
            if mid!='global' and m!=mid: continue
            for r in recs:
                if r['status']!='active': continue
                if layer is not None and r.get('layer')!=layer: continue
                res.append(r)
        return res

@pytest.fixture
def mc(): return MockMC()

@pytest.fixture
def engine(mc): return DeepReasoningEngine(mc)

class TestReasoning:
    def test_reason_returns_decision(self, engine):
        d = engine.reason({"objective":"deploy","risk_level":"low","mission_id":"m1"})
        assert isinstance(d, ReasoningDecision)
        assert d.normalized_goal == "deploy"
    def test_normalize_problem(self, engine):
        n = engine.normalize_problem("deploy api")
        assert n["goal"] == "deploy api"
    def test_detect_conflicts(self, engine):
        c = engine.detect_conflicts(["high_risk_execution","deployment_safety"])
        assert len(c) >= 1
    def test_detect_conflicts_none(self, engine):
        c = engine.detect_conflicts(["standard"])
        assert c == []
    def test_compare_strategies(self, engine):
        s = [{"name":"a","risk":0.5},{"name":"b","risk":0.1}]
        r = engine.compare_strategies(s)
        assert r[0]=="b"
    def test_counterfactual(self, engine):
        s = [{"name":"a"},{"name":"b"}]
        cf = engine.counterfactual("a",s)
        assert "b" in cf.get("alternatives",[])
    def test_emit_decision(self, engine, mc):
        d = engine.reason({"objective":"test","mission_id":"m1"})
        cid = engine.emit_decision(d)
        assert cid is not None
    def test_strategies_includes_multiple(self, engine):
        d = engine.reason({"objective":"deploy","risk_level":"low","mission_id":"m1"})
        assert len(d.candidate_strategies) >= 2
    def test_constraints_from_high_risk(self, engine):
        d = engine.reason({"objective":"x","risk_level":"high","mission_id":"m1"})
        assert any("high_risk" in c for c in d.constraints)
    def test_uncertainty_when_no_strategies(self, engine):
        engine._generate_alternatives = lambda g,h: []
        d = engine.reason({"objective":"x","mission_id":"m1"})
        assert d.confidence == 0.3

class TestSummary:
    def test_summarize(self, engine, mc):
        d = engine.reason({"objective":"x","mission_id":"m1"})
        engine.emit_decision(d)
        s = engine.summarize()
        assert s["total_decisions"] >= 1
