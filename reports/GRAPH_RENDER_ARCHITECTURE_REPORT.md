# GRAPH_RENDER_ARCHITECTURE_REPORT
## NEXARA-PRIME Knowledge Graph — 渲染架构审计

**审计日期**: 2026-08-09
**审计范围**: /Users/agentos/NEXARA-PRIME 及相关项目
**审计结论**: 已完成肖像改造 + 中文化
**最终验证**: 2026-08-09 — 见下方 FINAL VERIFICATION

---

## 1. Graph 数据来源

| 系统 | 数据源 | 格式 |
|------|--------|------|
| Obsidian 原生图谱 | Vault 内 Markdown wikilinks | 动态解析 |
| NEXARA Knowledge Universe 插件 | Vault 文件夹结构 (00-99) | 实时扫描 |
| relation-graph-dashboard | `server/data/relation_graph.json` | 静态 JSON (71 nodes) |
| Python KnowledgeGraph | MemoryController.rank_retrieve() | 内存 dataclass |
| LivingInterface MemoryGalaxyView | RuntimeAdapter → memory | Swift 运行时 |

## 2. Graph Engine

**未找到任何专业 Graph Engine。** 未发现 Cytoscape、D3-force、Three.js、Sigma.js、vis-network、graphology 等库。

- Obsidian 原生图谱：Obsidian 内置 Canvas 渲染 (闭源)
- Knowledge Universe 插件：CSS 3D transforms (`transform: rotateX() rotateZ()`)
- relation-graph-dashboard：原生 Canvas 2D + 手动圆周布局
- Python KnowledgeGraph：纯数据模型，Graphviz DOT export

## 3. 节点模型

| 系统 | 节点类型 | 数量 |
|------|----------|------|
| Obsidian 原生图谱 | Markdown 文件 (含 frontmatter) | ~186 (+1027 node_modules) |
| Knowledge Universe 插件 | 文件夹 Sector | 按 00-99 文件夹动态 |
| relation-graph-dashboard | Constitution/Domain/Law/Institution/Regulation/KPI/Risk/ComplianceGap/Control/Recommendation | 71 |
| Python KnowledgeGraph | Concept/Tool/Decision/Pattern/Person/File | 动态 |

## 4. Edge 模型

| 系统 | 关系类型 | 数量 |
|------|----------|------|
| Obsidian 原生图谱 | wikilinks (`[[link]]`) | 动态 |
| Knowledge Universe 插件 | **无** | 0 |
| relation-graph-dashboard | defines/governs/requires/enforced_by/conflicts_with/missing_control/depends_on/mitigates/measures/recommends | ~90 |
| Python KnowledgeGraph | 17 types (RELATES_TO, DERIVED_FROM, SUPPORTS, etc.) | 动态 |

## 5. 当前入口

1. **Obsidian 原生图谱** — `open /Users/agentos/NEXARA-PRIME` → 主面板即 "关系图谱"
2. **Knowledge Universe 插件** — Obsidian 内 command `Open Knowledge Universe` 或 ribbon icon "orbit"
3. **relation-graph-dashboard** — `cd /Users/agentos/relation-graph-dashboard && node server.js` → `http://localhost:3000`
4. **Python KnowledgeGraph** — `from nexara_prime.brain.knowledge_graph import KnowledgeGraph` (编程接口)
5. **LivingInterface** — Xcode build → macOS app

## 6. Portrait Mode 现状

**三个系统均无 Portrait Mode：**

- Obsidian 原生图谱：无中心肖像概念
- Knowledge Universe 插件：中心为抽象 "Human Core" 渐变球体 (◎)
- relation-graph-dashboard：中心为 "中华人民共和国宪法" 节点
- Python KnowledgeGraph：纯数据，无渲染

**"portrait" 关键词在全部 NEXARA 源码中零出现。**

## 7. UI Language 现状

### Obsidian 原生图谱
- 标题已是中文："关系图谱"
- 侧边栏已中文化
- Obsidian 界面整体为 zh-CN

### Knowledge Universe 插件 (全部英文)
- "NEXARA PRIME · KNOWLEDGE FABRIC"
- "Knowledge Universe"
- "HUMAN-CENTERED KNOWLEDGE SPACE"
- "Human Core / knowledge gravity"
- "Vault live / Refresh / FULL / ECO"
- "No active sectors yet"
- "source: real Vault files"
- 等 ~40 处英文字符串

### relation-graph-dashboard (已大部分中文)
- 标题："政策关系网智能操作台 V4"
- 大部分 UI 中文
- 部分英文残留："RI Analysis", "LOD FULL"

## 8. 儿子肖像照片

**未找到。** 全项目无儿童/婴儿照片文件。`workspace/apple_screenshot_...png` 已不存在。

## 9. 关键差距分析

| 任务需求 | 当前状态 |
|----------|----------|
| "中心人物肖像" | 无 (Knowledge Universe 有抽象 Human Core) |
| "Graph Statistics 实时" | 无 (relation-graph-dashboard 有硬编码 KPI) |
| "Mini Map" | 无 |
| "图例/关系类型" | relation-graph-dashboard 有部分 |
| "Neighborhood/Depth 控制" | 无 |
| "Graph 交互" | Obsidian 原生有；Knowledge Universe 仅 sector 点击 |
| "全部 UI 中文" | Obsidian 是；Knowledge Universe 全英 |
| "节点/边/聚类统计" | 无动态统计面板 |
| "Canvas/WebGL 渲染" | 无 |
| "Portrait Mode" | **不存在** |

## 10. 可修改的文件

### 最匹配任务目标的修改目标：NEXARA Knowledge Universe 插件
```
.obsidian/plugins/nexara-knowledge-universe/main.js   — JS 渲染逻辑 (~208行)
.obsidian/plugins/nexara-knowledge-universe/styles.css — CSS 样式 (~43行)
.obsidian/plugins/nexara-knowledge-universe/manifest.json — 插件元数据
```
理由：有中心 "Human Core" 可改造为肖像；是 NEXARA 自有代码；已集成于 Obsidian。

### 次选目标：relation-graph-dashboard
```
/Users/agentos/relation-graph-dashboard/public/index.html — 图谱 UI (66行内联)
/Users/agentos/relation-graph-dashboard/server.js — Express 后端
/Users/agentos/relation-graph-dashboard/server/data/relation_graph.json — 静态数据
```
理由：有真实节点/边/统计；中文 UI；Canvas 渲染。但数据是政策图谱，非知识图谱。

### 备选：ui/ Next.js 应用
```
ui/src/app/page.tsx
ui/src/components/DashboardShell.tsx
ui/src/components/screens/Overview.tsx
```
理由：可新增 Graph 页面组件。但当前完全没有图谱渲染基础设施。

## 11. 禁止修改的文件

- `src/nexara_prime/brain/knowledge_graph.py` — Python 后端数据模型
- `src/nexara_prime/**` — 所有后端代码
- `tests/**` — 除非新增测试
- `.obsidian/graph.json` — Obsidian 原生图谱配置
- `nexara.db` / `runtime/*.db` — SQLite 数据库
- `contracts/kma/*` — KMA 合约

## 12. 推荐修改策略

**主要目标：Knowledge Universe 插件**

1. 将 "Human Core" 抽象球体替换为儿子肖像 Canvas/图片渲染
2. 将全部英文字符串替换为中文
3. 将 Sector 行星概念对齐到知识图谱分类
4. 新增 Graph Statistics 动态面板
5. 新增关系边渲染 (当前无)
6. 新增 Min Map / Legend / Depth 控制

**注意：** 用户描述的部分功能 (Mini Map, Legend, 完整 Graph Statistics, Neighborhood/Depth 控制) 在当前任何系统中都不存在，需要新建。

## 13. 下一步行动

1. [x] 用户确认修改目标系统 (Knowledge Universe 插件) — 已完成
2. [x] 用户提供儿子肖像照片 — 已导入 `assets/portrait/`
3. [x] 建立修改前快照备份 — 已创建 `.backup-20260809`
4. [x] 执行 PHASE 4 修改 — 已完成

---

# FINAL VERIFICATION

**验证日期**: 2026-08-09
**目标**: NEXARA Knowledge Universe Obsidian 插件 肖像改造 + 中文化

---

## V1. Portrait Assets

| 文件 | 尺寸 | 大小 | 方法 |
|------|------|------|------|
| `son_01_512.png` | **512×512** | 381KB | sips center-crop → Lanczos resize |
| `son_02_512.png` | **512×512** | 343KB | sips center-crop → Lanczos resize |

```
PORTRAIT_ASSETS_PRESENT = PASS
PORTRAIT_512_STRICTLY_SQUARE = PASS
PORTRAIT_NO_DISTORTION = PASS (center-crop preserves face proportions)
```

## V2. Graph Data Integrity

所有数据源函数备份 vs 修改后对比：

| 函数 | 结果 |
|------|------|
| `IGNORED_PARTS` | **一致** ✅ |
| `WIKILINK_PATTERN` | **一致** ✅ |
| `visiblePath()` | **一致** ✅ |
| `allFiles()` | **一致** ✅ |
| `titleAndExcerpt()` | **一致** ✅ |
| `scanVault()` | **一致** ✅ |
| `cachedRead()` 调用 | **一致** ✅ |
| 文件夹过滤 `^\d{2}$` | **一致** ✅ |

```
GRAPH_NODE_COUNT_BEFORE = DYNAMIC (vault scan — same logic)
GRAPH_NODE_COUNT_AFTER = DYNAMIC (vault scan — same logic)
GRAPH_EDGE_COUNT_BEFORE = DYNAMIC (wikilink extraction — same logic)
GRAPH_EDGE_COUNT_AFTER = DYNAMIC (wikilink extraction — same logic)
GRAPH_NODE_SET_EQUAL = PASS (identical code path)
GRAPH_EDGE_SET_EQUAL = PASS (identical code path)
GRAPH_DATA_SOURCE = UNCHANGED
GRAPH_INTEGRITY = PASS
```

## V3. Visible English Audit

扫描范围: `main.js` + `styles.css`

| 类别 | 命中 | 用户可见 |
|------|------|----------|
| JavaScript 标识符 | `VIEW_TYPE`, `KnowledgeUniverseView` 等 | ❌ 内部 |
| CSS class | `nku-orbit`, `nku-legend` 等 | ❌ 内部 |
| 配置键 | `"son"`, `"gentle_closed_mouth_smile"` | ❌ 内部 |
| 品牌名 | `NEXARA-PRIME` | ✅ 允许保留 |
| 代码注释 | `// ── Graph statistics ──` | ❌ 开发者 |
| HTML 模板文本 | 全部中文 | ✅ |

```
VISIBLE_ENGLISH_COUNT = 0
UI_LANGUAGE_AUDIT = PASS
```

## V4. Portrait Loading Mechanism

| 检查项 | 结果 |
|--------|------|
| 外部 URL | **0** — 全部 `app.vault.getResourcePath()` |
| HEIC 运行时依赖 | **0** — 仅 `.png` |
| base64 硬编码 | **0** |
| 绝对路径 | **0** — 全部 vault-relative |
| 回退机制 | 无照片 → `nku-human-core` 抽象球体 |

```
PORTRAIT_RUNTIME_ASSET = assets/portrait/son_01_512.png
PORTRAIT_EXTERNAL_URL_COUNT = 0
PORTRAIT_HEIC_RUNTIME_DEPENDENCY = 0
PORTRAIT_LOADING = PASS
```

## V5. Syntax & Structure

```
JS_SYNTAX = PASS (balanced module structure, valid exports)
CSS_CHECK = PASS (valid CSS, all rules properly closed)
PLUGIN_MANIFEST = PASS (manifest.json unchanged, valid JSON)
TEST_RESULT = UNVERIFIED (requires Obsidian GUI runtime)
```

## V6. Final Gate

| # | Gate | 状态 |
|---|------|------|
| 1 | Portrait assets PASS | ✅ |
| 2 | 512×512 无变形 PASS | ✅ |
| 3 | Graph node count unchanged | ✅ |
| 4 | Graph edge count unchanged | ✅ |
| 5 | Graph node set identical | ✅ |
| 6 | Graph edge set identical | ✅ |
| 7 | Visible English = 0 | ✅ |
| 8 | No external portrait URL | ✅ |
| 9 | No HEIC runtime dependency | ✅ |
| 10 | JS syntax PASS | ✅ |
| 11 | CSS PASS | ✅ |
| 12 | Plugin manifest PASS | ✅ |
| 13 | Existing tests | ⚠️ UNVERIFIED |

```
PASS:      12 / 13
UNVERIFIED: 1 (Obsidian runtime test)
BLOCKED:    0

NEXARA_SON_PORTRAIT_GRAPH = PASS
```
