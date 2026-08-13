"use client";

import { EmptyState } from "@/components/ui/EmptyState";

/**
 * 记忆 — 浏览（批次 4 实现：映射真实分层
 * working/episodic/semantic/procedural × 14 kinds，无象限隐喻）
 */
export default function MemoryBrowsePage() {
  return (
    <EmptyState
      title="记忆浏览"
      description="记忆由运行时机按置信度自动沉淀（auto_commit），此视图将在后续批次接入 /api/memory。当前状态：尚未接入。"
    />
  );
}
