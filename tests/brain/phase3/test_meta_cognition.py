"""Tests: Meta-Cognition Controller."""
import pytest
from src.nexara_prime.brain.meta_cognition import MetaCognitionController
from src.nexara_prime.brain.cognitive_models import CognitiveAssessment

_LAYER = {"preference":"semantic","experience":"episodic","procedural":"procedural"}

class MockMC:
    def __init__(s): s.store = {}
    def commit(s,*a,**kw):
        mid=kw.get('mission_id',a[0]if a else''); key=kw.get('key',a[1]if len(a)>1 else'')
        content=kw.get('content',a[2]if len(a)>2 else''); kind=kw.get('kind',a[3]if len(a)>3 else'')
        s.store.setdefault(mid,[]).append({'mission_id':mid,'key':key,'content':content,'kind':kind,'layer':_LAYER.get(kind,kind),'evidence_id':'','confidence':1.0,'status':'active','weight':1.0})
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
def meta(mc): return MetaCognitionController(mc)

class TestAssessment:
    def test_assess_with_evidence(self, meta):
        ctx = {"known_facts":["fact a"],"evidence":["ev1","ev2","ev3"],"assumptions":["assume ok"]}
        a = meta.assess_knowledge_state("m1",ctx)
        assert a.confidence >= 0.7
        assert not a.human_escalation_required
    def test_assess_low_evidence(self, meta):
        a = meta.assess_knowledge_state("m1",{"known_facts":[],"evidence":[],"assumptions":["risky assumption"]})
        assert a.confidence <= 0.5
        assert len(a.evidence_gaps) >= 1
    def test_identify_unknowns(self, meta):
        u = meta.identify_unknowns(["a","b"],["a","b","c","d"])
        assert "c" in u
        assert "d" in u
    def test_validate_assumptions(self, meta):
        v = meta.validate_assumptions(["safe","risky"],["safe is ok"])
        assert v[0]["validated"]
        assert not v[1]["validated"]
    def test_detect_overconfidence(self, meta):
        a = CognitiveAssessment("id","m1",confidence=0.8,evidence_gaps=["g1","g2"])
        assert meta.detect_overconfidence(a)
    def test_detect_not_overconfident(self, meta):
        a = CognitiveAssessment("id","m1",confidence=0.5,evidence_gaps=[])
        assert not meta.detect_overconfidence(a)
    def test_calibrate(self, meta):
        c = meta.calibrate_confidence(CognitiveAssessment("id","m1"), 5, 2, 1)
        assert 0.1 <= c <= 1.0
    def test_require_escalation(self, meta):
        a = CognitiveAssessment("id","m1",contradiction_count=3,human_escalation_required=False)
        assert meta.require_escalation(a)
    def test_require_research(self, meta):
        a = CognitiveAssessment("id","m1",evidence_gaps=["g1"],unknowns=["u1","u2","u3"])
        assert meta.require_research(a)
    def test_stop_unsafe(self, meta):
        a = CognitiveAssessment("id","m1",confidence=0.8,evidence_gaps=["g"],contradiction_count=0)
        assert not meta.stop_unsafe(a)
        a2 = CognitiveAssessment("id","m2",contradiction_count=4)
        assert meta.stop_unsafe(a2)
    def test_record(self, meta, mc):
        a = meta.assess_knowledge_state("m1",{})
        cid = meta.record_assessment(a)
        assert cid is not None

class TestSummary:
    def test_summarize(self, meta, mc):
        a = meta.assess_knowledge_state("m1",{})
        meta.record_assessment(a)
        s = meta.summarize()
        assert s["total_assessments"] >= 1
