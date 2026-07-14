# Decision Log

## 2026-07-15 — G7 Native-First Product Strategy [ADR]

- **Decision:** Native-First Strategy. macOS is primary product surface. iPhone/iPad use independent native SwiftUI. Web is dev/debug/remote auxiliary — NOT primary product surface.
- **Rationale:** Blueprint §18 mandates independent Mac/iPhone/iPad layouts. WebView wrappers violate "no template-looking UI" and "three-platform independent design" requirements. Native SwiftUI enables Runtime Truth binding, reduced-motion support, and platform-specific UX.
- **Constraints:** No WebView wrapping. No mock data. No design-only deliverables. Must build, launch, and screenshot.
- **Signed:** Claude Code Prime — G7 Native-First

## 2026-07-15 — Program Fact Baseline Consolidation V1
- **Decision:** Execute NEXARA_PROGRAM_FACT_BASELINE_CONSOLIDATION_V1
- **Context:** `.nexara/` had 5 files pointing to 3 different gate names. Three core mother files were on Desktop but not in repo.
- **Signed:** Claude Code Prime

## 2026-07-10T23:16:06Z — Baseline Gate Start [DEPRECATED]
- **Decision:** Execute NEXARA_PRIME_REPOSITORY_BASELINE_AND_STATE_TRACKING_V1
- **Signed:** Hermes Agent / 小马
- **Status:** Superseded by Program Fact Baseline Consolidation V1 (2026-07-15)
