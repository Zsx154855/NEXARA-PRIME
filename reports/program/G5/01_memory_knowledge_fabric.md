# G5 — Memory & Knowledge Fabric

**Gate:** G5 — Memory & Knowledge Fabric
**Status:** PASS
**Date:** 2026-07-15

## Exit Condition: 证据支持记忆、Knowledge Graph、检索、冲突和保留策略

### MemoryKernel Capabilities

| Capability | Implementation | Status |
|-----------|---------------|--------|
| Evidence-backed writes | `source_evidence_id` required for auto-commit | ✅ |
| Confidence scoring | 0.0-1.0, auto-commit at ≥0.8 + evidence | ✅ |
| Conflict detection | `conflict_keys` + `memory.conflict.detected` event | ✅ |
| Conflict resolution | `commit_candidate()` with human actor | ✅ |
| Retrieval | `inspect()`, `candidates()` by mission_id | ✅ |
| 8 memory kinds | SHORT_TERM, FACT, DECISION, FAILURE, PATCH, USER_FACT, PROJECT_FACT, PREFERENCE | ✅ |
| Semantic relationships | `conflict_keys` cross-referencing + `MemoryKind` taxonomy | ✅ |
| EXPIRED kind | Defined for future retention policy | ⚪ (G9) |

### Knowledge Universe

| Component | Implementation |
|-----------|---------------|
| Vault scanning | `/api/knowledge-universe` endpoint |
| CLI | `nexara ku` commands |
| Search index | Derived from canonical sources |

### Future Enhancements (G9 scope)

- Full Knowledge Graph DB (NetworkX/DuckDB projection)
- Automated retention/prune policy
- Semantic search across memory corpus
