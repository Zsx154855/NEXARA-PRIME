"use client";

import { EmptyState } from "@/components/ui/EmptyState";

/** 治理 — 收据链（批次 4 接入 /api/receipts 懒加载整链校验） */
export default function TrustReceiptsPage() {
  return (
    <EmptyState
      title="收据链"
      description="收据整链校验按使命懒加载，此视图将在后续批次接入运行时数据源。当前状态：尚未接入。"
    />
  );
}
