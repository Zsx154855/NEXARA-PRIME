"use client";

import { EmptyState } from "@/components/ui/EmptyState";

/** 记忆 — 分层统计（批次 4 接入 /api/memory/stats 四层） */
export default function MemoryStatsPage() {
  return (
    <EmptyState
      title="记忆分层统计"
      description="working / episodic / semantic / procedural 四层统计，此视图将在后续批次接入 /api/memory/stats。当前状态：尚未接入。"
    />
  );
}
