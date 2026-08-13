"use client";

import { EmptyState } from "@/components/ui/EmptyState";

/**
 * 记忆 — 候选（批次 4 实现；如实呈现 auto_commit 机制，
 * 人工提交/驳回标 PLANNED——无对应 HTTP 端点）
 */
export default function MemoryCandidatesPage() {
  return (
    <EmptyState
      title="记忆候选"
      description="候选记忆由运行时机按置信度与证据绑定自动提交；人工审批记忆为 PLANNED 能力（后端无对应端点）。此视图将在后续批次接入 /api/memory/candidates。"
    />
  );
}
