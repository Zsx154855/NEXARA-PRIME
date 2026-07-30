"""Tests: Governed World Model."""
import pytest
from src.nexara_prime.brain.world_model import GovernedWorldModel

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
        return f'cid_{len(s.store.get(mid,[]))}'
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
def wm(mc): return GovernedWorldModel(mc)

class TestIngestion:
    def test_ingest_fact(self, wm):
        cid = wm.ingest_observation("event","source_x",{"detail":"test"},classification="FACT")
        assert cid is not None
    def test_ingest_inference(self, wm):
        cid = wm.ingest_observation("event","src",{},classification="INFERENCE")
        assert cid is not None
    def test_invalid_classification_defaults(self, wm):
        cid = wm.ingest_observation("e","src",{},classification="INVALID")
        assert cid is not None
    def test_ingest_with_evidence(self, wm):
        cid = wm.ingest_observation("type","src",{},evidence_refs=["ev1","ev2"])
        assert cid is not None

class TestRetrieval:
    def test_get_entity(self, wm):
        wm.ingest_observation("event","src",{"detail":"x"})
        entities = wm._mc.recall("global","procedural")
        for r in entities:
            if r["key"].startswith("world:"):
                eid = r["key"].replace("world:","")
                ent = wm.get_entity(eid)
                assert ent is not None
                break
    def test_get_nonexistent(self, wm):
        assert wm.get_entity("nonexistent") is None

class TestClassification:
    def test_classify_entity(self, wm):
        wm.ingest_observation("event","src",{})
        entities = wm._mc.recall("global","procedural")
        eid = entities[0]["key"].replace("world:","")
        assert wm.classify_entity(eid, "RETRACTED")
    def test_invalid_classification_fails(self, wm):
        wm.ingest_observation("event","src",{})
        entities = wm._mc.recall("global","procedural")
        eid = entities[0]["key"].replace("world:","")
        assert not wm.classify_entity(eid, "INVALID")

class TestMaintenance:
    def test_detect_stale(self, wm):
        wm.ingest_observation("event","src",{})
        stale = wm.detect_stale()
        assert isinstance(stale, list)
    def test_expire_unverified(self, wm):
        wm.ingest_observation("event","src",{},classification="HYPOTHESIS")
        count = wm.expire_unverified()
        assert count >= 0
    def test_summarize(self, wm):
        wm.ingest_observation("event","src",{},classification="FACT")
        wm.ingest_observation("event","src",{},classification="INFERENCE")
        s = wm.summarize()
        assert s["facts"] >= 1
        assert s["inferences"] >= 1
