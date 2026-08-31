import sys
sys.path.insert(0, "/Volumes/NEXARA/NEXARA-PRIME/src")
from pathlib import Path
from nexara_prime.db import SQLiteStore
from nexara_prime.events import EventBus
from nexara_prime.memory import MemoryKernel, MemoryKind
from nexara_prime.memory_archive import MemoryArchive

DB = Path("/Volumes/NEXARA/NEXARA-PRIME/runtime/nexara.db")
store = SQLiteStore(DB)
events = EventBus(store)
mk = MemoryKernel(store, events)

# 1. Memory A (committed/active)
a = mk.write(MemoryKind.FACT, key="gap-closure-mem", content="v1", trace_id="t1", mission_id=None)
print("mem A:", a.memory_id)

# 2. Memory B (same key, supersedes A)
b = mk.write(MemoryKind.FACT, key="gap-closure-mem", content="v2", trace_id="t2", mission_id=None)
print("mem B:", b.memory_id)

a_raw = store.get_record(a.memory_id)
print("A status after B:", a_raw.get("status"), "| superseded_by:", a_raw.get("superseded_by"))

# 3. archive A
arch = MemoryArchive(store)
r = arch.archive_memory(a.memory_id, reason="superseded by B", superseded_by=b.memory_id)
print("archived A:", r.status, "| archived_at set:", bool(r.archived_at), "| superseded_by:", r.superseded_by)

# 4. restart + verify
store2 = SQLiteStore(DB)
a2 = store2.get_record(a.memory_id)
b2 = store2.get_record(b.memory_id)
print("restart A:", a2.get("status"), "| archived_at:", bool(a2.get("archived_at")), "| superseded_by:", a2.get("superseded_by"))
print("restart B:", b2.get("status"))

# 5. retrieval policy
arch2 = MemoryArchive(store2)
active = arch2.list_active()
archived = arch2.list_archived()
print("active_excludes_archived:", all(r.get("status") != "archived" for r in active))
print("A_in_archived_list:", any(r.get("memory_id") == a.memory_id for r in archived))
print("A_MEMORY_ID:", a.memory_id)
print("B_MEMORY_ID:", b.memory_id)
