# AEP-03｜隔离容器合成实验摘要

> **本文件不是 Mac 验收，也不是 OpenMausBot 三 Agent 执行回执。** 仅记录 2026-11-08 在 ChatGPT 隔离工具容器运行的无敏感合成代码测试结果。原始日志未公开发布。

| 实验 | 真实 OS 测试退出码 | 结果 | 原始日志 SHA-256 |
|---|---:|---|---|
| Task A，修复前 | 1 | FAIL（预期缺陷） | `533e414db4cc7b198f09a22e81b076a5069af1f78fb1e1f083444a2a170ff826` |
| Task A，人工最小修复后 | 0 | PASS | `245ac0df4363c96f49b18686251ffeb4fa45d0f10b3b25ff4ed06417e2977596` |
| Task B 对照组，修复前 | 1 | FAIL（预期缺陷） | `5b2987409f3d4470902d7c6d8bfc7964d2d7d3a80bbf159ab39f2320a71b530c` |
| Task B 记忆组，修复前 | 1 | FAIL（预期缺陷） | `99c9d27e74383dc80e34c46e6662e1493b5315aa4984e16ebeefa90a0f70c32b` |

- Task A 原始测试哈希（前后相同）：`15b7e1ed189cd6bb0bcae3bde6f2fd6d6b031d471cd105c47c11b5e9062a708c`。
- Task A 最小修改的补丁哈希：`9f5d99be374e9dc97a21c69eaa29276621bea4bd620eb31325c2985c36df8009`。
- Task B 两组原始测试哈希：`870fb410557f3cfba3f133e0e5faf9f004c78a18a7e0d10d43497faebdcb9253`。
- 原始验收测试被改动时拒绝：`tests_modified_since_synthetic_baseline`。
- 本轮新增付费模型调用：`0`。Mac 原生测试、OpenMausBot 三 Agent、独立 QA、NEXARA A→B 经验迁移均为 `NOT_VERIFIED`。

真实合成项目生成器、预检和测试工具见 [aep03_local_gate.py](./aep03_local_gate.py)，完整 Mac 接管任务见 [AEP03_MASTER_HANDOFF.md](./AEP03_MASTER_HANDOFF.md)。原始日志留在当前会话工作容器，不将未复核日志上传公开仓库。
