"use client";

import { EvidenceViewer } from "@/components/screens/EvidenceViewer";
import { useRuntimeData } from "@/lib/runtime-context";

/** 治理 — 证据链 */
export default function TrustEvidencePage() {
  const { api, overview } = useRuntimeData();
  return <EvidenceViewer api={api} overview={overview} />;
}
