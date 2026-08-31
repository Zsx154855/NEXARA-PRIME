import sys
sys.path.insert(0, "/Volumes/NEXARA/NEXARA-PRIME/src")
from pathlib import Path
from nexara_prime.db import SQLiteStore
from nexara_prime.session_persistence import SQLiteSessionStore

DB = Path("/Volumes/NEXARA/NEXARA-PRIME/runtime/nexara.db")

# 1. 创建 Session A (真实 DB)
store = SQLiteStore(DB)
ss = SQLiteSessionStore(store)
sa = ss.create_session(user_id="gap-closure-verify")
print("created:", sa.id, sa.status.value)

ss.add_conversation(sa.id, "conv-gap-closure-test")
sa = ss.get(sa.id)
print("after add_conv:", sa.id, "convs:", sa.conversation_ids)

# 2. 验证 SQLite 真实存在 session record
raw = store.get_record(sa.id)
print("sqlite_record_exists:", raw is not None, "| status:", raw["status"] if raw else None)

# 3. 模拟 restart (重新开 store)
store2 = SQLiteStore(DB)
ss2 = SQLiteSessionStore(store2)
sa2 = ss2.get(sa.id)
print("after_restart:", sa2.id, sa2.status.value, "convs:", sa2.conversation_ids, "ver:", sa2.version)
print("SAME_SESSION_ID:", sa2.id == sa.id)
print("SAME_CONVERSATIONS:", sa2.conversation_ids == sa.conversation_ids)
print("SESSION_ID:", sa.id)
