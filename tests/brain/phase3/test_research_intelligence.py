"""Tests: Research Intelligence Engine."""
import pytest
from src.nexara_prime.brain.research_intelligence import ResearchIntelligenceEngine

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
def research(mc): return ResearchIntelligenceEngine(mc)

class TestResearch:
    def test_create_task(self, research):
        t = research.create_task("What is X?","general",10,3600)
        assert t.question == "What is X?"
        assert t.budget_limit == 10
    def test_extract_claims(self, research):
        sources = [{"source":"a","content":"claim text"}]
        claims = research.extract_claims(sources)
        assert len(claims) == 1
    def test_map_claims_to_evidence(self, research):
        claims = [{"claim_id":"c1","statement":"test fact about AI"}]
        evidence = [{"id":"ev1","summary":"test fact about AI confirmed"}]
        mapped = research.map_claims_to_evidence(claims, evidence)
        assert mapped[0]["supporting"] == 1
    def test_detect_contradictions(self, research):
        claims = [
            {"claim_id":"a","classification":"FACT"},
            {"claim_id":"b","classification":"INFERENCE"},
        ]
        c = research.detect_contradictions(claims)
        assert len(c) >= 1
    def test_no_contradictions(self, research):
        claims = [
            {"claim_id":"a","classification":"FACT"},
            {"claim_id":"b","classification":"FACT"},
        ]
        c = research.detect_contradictions(claims)
        assert len(c) == 0
    def test_assess_source_quality(self, research):
        sources = [{"source":"reliable","confidence":0.9},{"source":"unreliable","confidence":0.1}]
        scores = research.assess_source_quality(sources)
        assert scores["reliable"] > scores["unreliable"]
    def test_synthesize(self, research):
        claims = [{"claim_id":"c1","confidence":0.8},{"claim_id":"c2","confidence":0.3}]
        s = research.synthesize(claims)
        assert s["total_claims"] == 2
        assert s["average_confidence"] > 0.5
    def test_emit_brief(self, research, mc):
        t = research.create_task("Q")
        claims = research.extract_claims([{"source":"s","content":"answer"}])
        synth = research.synthesize(claims)
        cid = research.emit_brief(t, claims, synth)
        assert cid is not None
    def test_budget_constrained(self, research):
        t = research.create_task("Big question",budget=0)
        assert t.budget_limit == 0

class TestSummary:
    def test_summarize(self, research, mc):
        t = research.create_task("Q")
        claims = research.extract_claims([{"source":"s","content":"a"}])
        synth = research.synthesize(claims)
        research.emit_brief(t, claims, synth)
        s = research.summarize()
        assert s["total_research_tasks"] >= 1
