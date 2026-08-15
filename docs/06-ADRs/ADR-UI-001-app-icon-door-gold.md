# ADR-UI-001 — NEXARA App Icon：门 + 金点

- 状态：ACCEPTED（2026-08-14 设计综合 PHASE 6；2026-08-15 V1.1 资产落地）
- 关联：Hermes 视觉批评（无记忆点批评 + 两个改进方向）、12_design_synthesis.md §2

## 背景

NEXARA 需要独立可辨的品牌图标。草案 Concept「晨井/方中之定」（方中方）被 Hermes 视觉批评否决：正确但不可区分（目标/取景框/井字原型泛滥）、与 AI 产品零联想。

## 决策

选「**门 + 金点**」：

1. 外方（石墨 #322F2A 圆角方）= 秩序容器
2. 右上角断口 = 门（语义：治理不是牢笼，人类随时接管/回滚，命中 ADR-002 Human-First Governance）
3. 内芯中心金点（香槟金 #C4A45A）= 完成/批准时刻，「金只亮一次」的品牌纪律进入 icon 本体

## 后果

- 正面：16px 可辨（外方+断口+单点）；区分度最高（断口一笔脱离方中方原型）；语义与治理叙事一致；light/dark 通用（石墨底）
- 负面：与「智能/AI」联想较弱——由 wordmark「柏韩·NEXARA」与产品叙事补偿
- 资产：SVG 源 ui/src/app/icon.svg；PNG 16-1024 全档 + mono（brand_gate_1_0，cairosvg 矢量直渲）；Web favicon + BrandMark.tsx + macOS/iOS 主图标（2026-08-15 接线，旧系备份为 *_legacy.png）

## 备选（记录，未采纳）

- Concept A「晨井/方中之定」：正确但无记忆点
- 改进 B「可打开的门」（右上断口 + 中心金点）：即被采纳方案
- 改进 A「井中上升之物」：未采用（元素多，16px 信息密度过高）
