"use client";

import { EvidenceChainScreen } from "@/components/screens/trust/EvidenceChainScreen";
import { useRuntimeData } from "@/lib/runtime-context";

/** 治理 — 证据链（getEvidence 投影 + EvidenceChain 组件） */
export default function TrustEvidencePage() {
  const { api, overview } = useRuntimeData();
  return <EvidenceChainScreen api={api} overview={overview} />;
}
