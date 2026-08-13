"use client";

import { EmptyState } from "@/components/ui/EmptyState";

/** 治理 — 审计（批次 4 接入 /api/events 按对象重放） */
export default function TrustAuditPage() {
  return (
    <EmptyState
      title="审计日志"
      description="审计事件按对象重放查看，此视图将在后续批次接入运行时数据源。当前状态：尚未接入。"
    />
  );
}
