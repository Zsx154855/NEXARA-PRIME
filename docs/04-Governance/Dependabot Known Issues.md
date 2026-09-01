# Dependabot Known Issues

登记无法立即修复、经评估接受风险的 Dependabot 告警。每条记录包含：告警标识、评估证据、接受理由、重开条件。

---

## KI-2026-001 · glib VariantStrIter 非健全性（告警 #23，中危）

- **日期**：2026-09-02
- **告警**：Dependabot #23 · GHSA-wrw7-89jp-8q8g · `ui/src-tauri/Cargo.lock` 中 `glib 0.18.5`（修补版 ≥0.20.0）
- **问题**：`glib::VariantStrIter` 的 `Iterator` / `DoubleEndedIterator` 实现存在非健全性（unsoundness）

### 评估证据

1. **零使用**：项目 Rust 源码（`ui/src-tauri/src`、`build.rs`）经全量检索，无任何 `glib` 直接引用，更未使用 `VariantStrIter`；glib 仅作为传递依赖出现在 Cargo.lock
2. **平台隔离**：glib 由 tauri 2.11.5 的 gtk3/webkit2gtk 栈引入，仅在 Linux 目标编译；当前发布目标为 macOS 桌面 + Cloudflare Pages Web，均不编译该依赖链
3. **无升级路径**：修补版 glib 0.20 属 gtk4 系，与 tauri 当前 gtk3 栈不兼容，无法单独提升；需等上游 Tauri/gtk-rs 迁移

### 接受理由

风险不可达（未使用受影响 API + 不在发布目标的编译链中），且修复受上游约束。评级：可容忍风险（tolerable risk）。

### 重开条件

- 上游 Tauri/gtk-rs 迁移至 glib ≥0.20 的依赖栈后，升级并移除本记录
- 项目新增 Linux 构建/发布目标时重新评估
- 出现该漏洞的活跃利用（in-the-wild exploitation）时立即重新评估
