# NEXARA CHANGELOG

## [0.1.0] — 2026-08-15（Unreleased / Release Candidate）

### Product Redesign V1.1
- Web：六区 IA（19 路由）+ Quiet Editorial Spatial 设计系统 + 门+金点品牌 + Onboarding 七步 + P1 数据边界隔离
- macOS：六区产品壳（端口 8765 统一、CONVERSATION 新页、版本号 0.1.0）
- iOS：六区产品壳（TabView/SplitView 自适应、真实对话视图、版本号 0.1.0）
- 品牌资产：brand_gate_1_0（门+金点 PNG 16-1024 + mono，cairosvg 矢量直渲）

### 验证
- Web：tsc strict / eslint / build 19-19 静态导出全绿；node:test 8/8（presentation boundary）
- 后端：pytest 2059 passed（5 环境失败=脏工作树 receipt 校验）；API smoke 13/13
- 双端：xcodebuild macOS + iOS（iPhone 15 Pro Max 模拟器）BUILD SUCCEEDED
- 审查：Hermes 产品/视觉/像素/终审/Re-audit 多轮，P0/P1/P2=0

### 已知限制
- AUTH = SHELL_ONLY（判定书 V11_AUTH_DECISION.md；PROHIBIT-03 禁多用户）
- Runtime QA 视觉层 = 待人工（浏览器/模拟器人工冒烟）
- 前端单测仅 presentation boundary（vitest 依赖安装权限受阻，node:test 替代）
