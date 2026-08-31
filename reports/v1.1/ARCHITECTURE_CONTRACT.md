# NEXARA V1.1 AGENT OPERATING LAYER — ARCHITECTURE CONTRACT

状态: V1_0_SEALED → BASELINE_VERIFIED ✓
原则: V1.0 = execution substrate (冻结), V1.1 = operating layer (新增, 不改 V1.0 Core)

## 对象模型 (14 一级域对象)
User → Session → Conversation → Agent → Mission → Execution → (Recovery | Evidence) → Memory → Evaluation → Token/Cost Governor → Control Plane → Audit/Telemetry

V1.0 已有一级对象: Session(session.py+persistence), Conversation(conversations.py), Mission(runtime.py), Execution, Recovery(recovery.py+error_taxonomy), Evidence(evidence.py), Memory(memory.py+archive), Evaluation
V1.1 需补一级对象: Agent, TokenUsage(正式), CostRecord(正式), AuditEvent(正式), RuntimeVersion(正式)

## V1.1 状态机
V1_0_SEALED → BASELINE_VERIFIED(✓) → V1_1_BOOTSTRAP → SESSION_READY → RECOVERY_READY → MEMORY_READY → COST_READY → CONTROL_PLANE_READY → UPGRADE_READY → PRODUCT_LOOP_READY → FINAL_ACCEPTANCE → V1_1_SEALED

## P0/P1 子系统 (新增 L2/L3 模块, 禁改 V1.0 Core)
P0 Session Layer: session_api.py (CREATE/GET/UPDATE_SESSION, CREATE_CONVERSATION, BIND_CONVERSATION_TO_SESSION, APPEND_MESSAGE, LOAD_CONTEXT, CREATE_MISSION, BIND_MISSION)
P0 Recovery Engine: recovery_runtime.py (error_taxonomy + policy + executor 集成)
P1 Memory OS: memory_os.py (5类型 + provenance + 完整生命周期)
P1 Token/Cost Governor: cost_governor.py (5层预算 + OBSERVE/ESTIMATE/LIMIT/WARN/BLOCK/DEGRADE/AUDIT)
P1 Control Plane: control_plane.py (统一 READ_ONLY 观察: status/health/sessions/conversations/missions/agents/executions/memory/tokens/cost/failures/recovery/audit/versions)
P1 Upgrade Manager: upgrade_manager.py (Preflight→Snapshot→Upgrade→Migration→Health→Canary→Acceptance→Seal; 失败→Rollback→Health→Evidence)
P2 Product Loop: 真实 Runtime 完整闭环验证

## 铁律
- CORE_RUNTIME_DRIFT=0 (禁改 V1.0 Core/SQLite/Provider/Governance/Mission/Launchd/Rollback)
- 触碰 V1.0 需 CHANGE_REQUEST+CONTRACT+IMPACT+MIGRATION+REGRESSION+ROLLBACK
- NO-FALSE-PASS (L0-L6 验收等级, 只有 L6=VERIFIED PASS 才推进)
- Single writer per mutable domain
