"use client";

import { ApprovalCenter } from "@/components/screens/ApprovalCenter";
import { useRuntimeData } from "@/lib/runtime-context";

/** 治理 — 审批收件箱（GET 投影 + mission approve 触发面） */
export default function TrustApprovalsPage() {
  const { api } = useRuntimeData();
  return <ApprovalCenter api={api} />;
}
