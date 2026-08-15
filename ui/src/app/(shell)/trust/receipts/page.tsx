"use client";

import { ReceiptChainScreen } from "@/components/screens/trust/ReceiptChainScreen";
import { useRuntimeData } from "@/lib/runtime-context";

/** 治理 — 收据链（getReceipts 按使命懒加载整链校验） */
export default function TrustReceiptsPage() {
  const { api, overview } = useRuntimeData();
  return <ReceiptChainScreen api={api} overview={overview} />;
}
