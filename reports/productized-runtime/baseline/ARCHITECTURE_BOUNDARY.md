# ARCHITECTURE BOUNDARY (L0/L1/L2 现状)

结论: L0/L1 成熟, L2 部分已有(分散) + 正式对象模型缺失.

L0 CORE (已有, 禁改):
  models.py / runtime.py / evidence.py / memory.py / policy_service.py
  db.py / events.py / tools.py / governance / kernel_boundary.py

L1 RUNTIME (已有):
  model_gateway.py + model_router.py (Provider)
  tools.py (Tool) / recovery (runtime.py: checked=67 resumable=1 dup=0)

L2 PRODUCTIZED RUNTIME (部分已有):
  Conversation: conversations.py + conversation_intent.py ✓
  Mission: runtime.py (checkpoint/resume/recovery) ✓
  Memory: memory.py + brain/memory_controller.py + long_term_memory.py ✓
  Token/Cost: telemetry.py + token_compiler.py + resource_budget.py + model_gateway(cost) ✓部分
  Health/Metrics: api.py (health/stats/overview) ✓
  Supervisor: launchd ✓
  Audit: connectors/audit.py + audit_entry(DB 701条) ✓部分
  Version/Rollback: ✗缺失(无 manifest)
  Session(独立于 conversation): ✗缺失
  正式对象模型(16 class): ✗缺失(分散无正式 class)

缺口: ①正式对象模型 ②version manifest ③独立 Session 生命周期
