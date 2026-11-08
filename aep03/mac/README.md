# AEP-03 本地执行接管包

此包供已获用户授权的 **Mac 本地 Agent** 使用。它不能从 ChatGPT 工具容器直接连接 Mac，也不代表真正运行了 OpenMausBot。

文件：
- `AEP03_MASTER_HANDOFF.md`：完整、不可拆分的真实三 Agent 实验总控任务书。
- `aep03_local_gate.py`：零依赖的环境预检、真实合成代码 Git 项目生成和原生测试回执。不会安装、启动 OpenMausBot 或购买模型。
- `SHA256SUMS.txt`：验证包内关键文件是否损坏。

在 Mac 上只需把整个包交给已有 OpenMinis、Codex 或 Claude 主控，并执行完整任务书。默认先运行 `python3 aep03_local_gate.py probe --repo /真实路径/NEXARA-PRIME --out ./preflight.json`，**而不是直接运行带工具权限的 Agent**。

若 OpenMausBot 服务、授权的零新增费用模型或隔离环境不具备，请提交预检结果并标记 `LIVE_EXECUTION_BLOCKED`，不允许用 fake CLI 代替。

本包脚本运行的所有 Python 合成测试是实际 OS subprocess，但不构成 macOS 全仓或三 Agent 工作证明；必须从真实 OpenMausBot 的任务、工具和测试回执独立验证。
