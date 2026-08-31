# G13 PRODUCT_LOOP (真实产品循环)

流程验证:
1. conversation 建立: conversation_2d1674f0dded ✓
2. 连续对话+历史上下文: chat2 正确复述 chat1 内容 ✓ (provider=deepseek, 真实推理)
3. mission 触发: intent=mission, approval_required=true → mission_2ae64ccf6948 ✓
4. approval: → Execution ✓
5. run: → Failed ✗  terminal_reason=tool_idempotency_conflict

失败详情:
- evidence=17, receipt=present, eval=not_evaluated
- events: tool.invoked[code-check] → tool.invoked[report-write] → mission.state_changed[Execution→Failed]
- 根因: report-write tool 幂等冲突, mission 未 graceful recovery 直接 Failed
- tool_claim 幂等键含 mission_id(无跨mission碰撞), events 全库无重复幂等键
- 判定: tool 执行层幂等检查触发 conflict, 但 recovery 层缺该错误的分类与降级处理

判定: G13 = FAIL (mission 部分真实失败, 暴露 tool 幂等/recovery 缺口)
