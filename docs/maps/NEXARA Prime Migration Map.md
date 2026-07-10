---
id: NEXARA-PRIME-MIGRATION-MAP
title: NEXARA Prime Migration Map
type: migration-map
status: canonical
owner: human
source_of_truth: git
runtime_effect: indirect
created_at: 2026-07-11
updated_at: 2026-07-11
supersedes: []
related: []
tags: [migration-map, knowledge-fabric]
---
# NEXARA PRIME Migration Map

当前仓库：`/Users/agentos/NEXARA-PRIME`

## 已有实现 → Knowledge Fabric

| NEXARA PRIME | Knowledge Fabric |
|---|---|
| `README.md` | [[01-Product/Product North Star]] + [[03-Runtime/Runtime Truth]] |
| `docs/ARCHITECTURE.md` | [[02-Architecture/Three-Layer Model]] + [[02-Architecture/12-Layers/README]] |
| `docs/GOVERNANCE.md` | [[04-Governance/Source of Truth Policy]] |
| `docs/TOOL_RUNTIME.md` | [[02-Architecture/12-Layers/L06 Tools]] + ADR-004 |
| `docs/EVALUATION.md` | [[02-Architecture/12-Layers/L12 Evolution]] |
| `reports/production_hardening/` | [[09-Evidence-Index/README]] |
| `tests/test_hardening.py` | [[08-Failure-Cases/README]] |
| `ui/` | [[05-UI-UX/UI Truth Contract]] |

## 当前审查阻断项

- 工具执行仍需要 OS 级沙箱。
- Approval 需要绑定实际动作和资源。
- Evidence 需要完整元数据链和不可变验证。
- Memory Patch 需要验证 Evidence 归属。
- Recovery 和 Rollback 需要真实中断恢复与补偿测试。

本映射只记录迁移关系，不复制 Runtime 数据和 Secret。
