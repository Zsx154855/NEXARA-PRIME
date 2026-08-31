import sys, json, urllib.request
sys.path.insert(0, "/Volumes/NEXARA/NEXARA-PRIME/src")
from pathlib import Path
from nexara_prime.db import SQLiteStore
from nexara_prime.session_api import SessionLayer
from nexara_prime.v1_1_objects import Agent, AgentStatus, TokenUsage, CostRecord, AuditEvent
from nexara_prime.events import EventBus
from nexara_prime.memory import MemoryKernel, MemoryKind

DB = Path("/Volumes/NEXARA/NEXARA-PRIME/runtime/nexara.db")
BASE = "http://127.0.0.1:8765"
store = SQLiteStore(DB)

def post(url, data):
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers={"Content-Type": "application/json"}, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=180).read())

# 1. Session + Agent
sl = SessionLayer(store)
s = sl.create_session("v11-product-loop")
a = Agent.create("executor-1", model="deepseek-v4-pro", provider="deepseek")
a.transition(AgentStatus.READY)
print("session:", s.id, "| agent:", a.id, a.status.value)

# 2. 真实 conversation
conv = post(f"{BASE}/api/conversations", {"title": "v11-product-loop"})
cid = conv["conversation_id"]
sl.bind_conversation(s.id, cid)
print("conversation:", cid)

# 3. 真实 mission
m = post(f"{BASE}/api/missions", {"objective": "生成运行状态简报", "source_dir": "."})
mid = m["mission_id"]
a.bind_mission(mid)
sl.bind_mission(s.id, mid)
print("mission:", mid)

# 4. run (approval not required for this mission)
run = post(f"{BASE}/api/missions/{mid}/run", {})
print("mission run:", run.get("detail") or run.get("current_state") or "ok")

# 5. Memory (真实路径)
events = EventBus(store)
mk = MemoryKernel(store, events)
mem = mk.write(MemoryKind.FACT, key="v11-loop-fact", content="V1.1 product loop verified", trace_id="v11", mission_id=mid)
print("memory:", mem.memory_id, "| status:", store.get_record(mem.memory_id).get("status"))

# 6. Token / Cost / Audit
t = TokenUsage(input_tokens=100, output_tokens=50, provider="deepseek", model="deepseek-v4-pro", session_id=s.id, mission_id=mid)
c = CostRecord(token_usage_id=t.id, scope="mission", provider="deepseek", model="deepseek-v4-pro")
e = AuditEvent(actor="agent", action="bind_mission", target_id=mid)
print("token:", t.total_tokens, "| cost scope:", c.scope, "| audit:", e.action)

# 7. context
ctx = sl.load_context(s.id)
print("context convs:", ctx["conversation_ids"], "missions:", ctx["mission_ids"])
print("AGENT_MISSIONS:", a.mission_ids)
print("SESSION_ID:", s.id)
print("MISSION_ID:", mid)
