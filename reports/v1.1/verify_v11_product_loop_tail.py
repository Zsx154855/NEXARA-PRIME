import sys
sys.path.insert(0, "/Volumes/NEXARA/NEXARA-PRIME/src")
from pathlib import Path
from nexara_prime.db import SQLiteStore
from nexara_prime.session_api import SessionLayer
from nexara_prime.v1_1_objects import TokenUsage, CostRecord, AuditEvent
from nexara_prime.events import EventBus
from nexara_prime.memory import MemoryKernel, MemoryKind

DB = Path("/Volumes/NEXARA/NEXARA-PRIME/runtime/nexara.db")
store = SQLiteStore(DB)
sid = "session_e2e5c58c1f96"
mid = "mission_24398a7b0915"
cid = "conversation_c408d443b1cc"

# 1. Memory 写入 (真实 mission)
events = EventBus(store)
mk = MemoryKernel(store, events)
mem = mk.write(MemoryKind.FACT, key="v11-loop-fact", content="V1.1 product loop verified", trace_id="v11", mission_id=mid)
print("memory:", mem.memory_id, "| status:", store.get_record(mem.memory_id).get("status"))

# 2. Token / Cost / Audit
t = TokenUsage(input_tokens=100, output_tokens=50, provider="deepseek", model="deepseek-v4-pro", session_id=sid, mission_id=mid)
c = CostRecord(token_usage_id=t.id, scope="mission", provider="deepseek", model="deepseek-v4-pro")
e = AuditEvent(actor="agent", action="bind_mission", target_id=mid)
print("token:", t.total_tokens, "| cost:", c.scope, "| audit:", e.action)

# 3. context load + restart 恢复
sl = SessionLayer(store)
ctx = sl.load_context(sid)
store2 = SQLiteStore(DB)
ctx2 = SessionLayer(store2).load_context(sid)
print("context convs:", ctx["conversation_ids"], "missions:", ctx["mission_ids"])
print("restart convs:", ctx2["conversation_ids"], "missions:", ctx2["mission_ids"])
print("CONTEXT_CONTINUITY:", ctx2["conversation_ids"] == ctx["conversation_ids"] and ctx2["mission_ids"] == ctx["mission_ids"])
print("MEMORY_ID:", mem.memory_id)
