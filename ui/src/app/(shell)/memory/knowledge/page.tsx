"use client";

import { EmptyState } from "@/components/ui/EmptyState";

/** 记忆 — 知识（批次 4 接入 /api/knowledge-universe） */
export default function MemoryKnowledgePage() {
  return (
    <EmptyState
      title="知识宇宙"
      description="文档库扫描视图，此视图将在后续批次接入 /api/knowledge-universe。当前状态：尚未接入。"
    />
  );
}
