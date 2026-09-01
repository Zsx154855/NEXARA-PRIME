import sys
sys.path.insert(0, "/Volumes/NEXARA/NEXARA-PRIME/src")
from pathlib import Path
from nexara_prime.db import SQLiteStore
from nexara_prime.session_api import SessionLayer
from nexara_prime.control_plane import ControlPlane
from nexara_prime.cost_governor import TokenGovernor
from nexara_prime.recovery_runtime import RecoveryExecutor

DB = Path("/Volumes/NEXARA/NEXARA-PRIME/runtime/nexara.db")
store = SQLiteStore(DB)

# 1. Session Layer 真实 DB + restart
sl = SessionLayer(store)
s = sl.create_session("v11-real-verify")
sl.bind_conversation(s.id, "conversation_f85074e77eb9")
sl.bind_mission(s.id, "mission_73c4eb1f8b5f")
ctx = sl.load_context(s.id)
print("session:", ctx["session"]["session_id"], "convs:", ctx["conversation_ids"], "missions:", ctx["mission_ids"])

store2 = SQLiteStore(DB)
sl2 = SessionLayer(store2)
ctx2 = sl2.load_context(s.id)
print("restart convs:", ctx2["conversation_ids"], "missions:", ctx2["mission_ids"])
print("SESSION_CONTINUITY:", ctx2["conversation_ids"] == ctx["conversation_ids"] and ctx2["mission_ids"] == ctx["mission_ids"])

# 2. Control Plane 真实统计
cp = ControlPlane(store)
summ = cp.summary()
print("control_plane:", {k: summ.get(k) for k in ("mission", "conversation", "memory", "session", "evidence", "audit_entry", "tool")})

# 3. Recovery + Cost
re = RecoveryExecutor()
print("recovery TOOL_IDEMPOTENCY_CONFLICT ->", re.classify("TOOL_IDEMPOTENCY_CONFLICT").get("recovery_strategy"))
tg = TokenGovernor()
tg.set_budget("mission", "m-test", 100)
print("cost usage1:", tg.record_usage("mission", "m-test", 50, None))
print("cost usage2:", tg.record_usage("mission", "m-test", 60, None))

print("V11_SESSION_ID:", s.id)
