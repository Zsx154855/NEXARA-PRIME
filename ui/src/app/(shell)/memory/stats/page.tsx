"use client";

import { MemoryStatsScreen } from "@/components/screens/memory/MemoryStatsScreen";
import { useRuntimeData } from "@/lib/runtime-context";

/** 记忆 — 分层统计（/api/memory/stats 四层真实计数，无象限隐喻） */
export default function MemoryStatsPage() {
  const { api } = useRuntimeData();
  return <MemoryStatsScreen api={api} />;
}
