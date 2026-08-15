"use client";

import { AuditTrailScreen } from "@/components/screens/trust/AuditTrailScreen";
import { useRuntimeData } from "@/lib/runtime-context";

/** 治理 — 审计（getEvents 按对象重放事件流） */
export default function TrustAuditPage() {
  const { api, overview } = useRuntimeData();
  return <AuditTrailScreen api={api} overview={overview} />;
}
