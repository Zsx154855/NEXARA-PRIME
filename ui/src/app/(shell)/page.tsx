"use client";

import { useRouter } from "next/navigation";
import { Overview } from "@/components/screens/Overview";
import { useRuntimeData } from "@/lib/runtime-context";
import { missionDetailPath } from "@/lib/navigation";

/**
 * HOME — 值班视角（批次 3 产品化）。
 * 批次 2 挂载现有 Overview，保持功能不断。
 */
export default function HomePage() {
  const { overview, stats, memoryStats, loading, error } = useRuntimeData();
  const router = useRouter();

  return (
    <Overview
      overview={overview}
      stats={stats}
      memoryStats={memoryStats}
      loading={loading}
      error={error}
      onMissionSelect={(missionId) => router.push(missionDetailPath(missionId))}
      onCreateMission={() => router.push("/missions/new")}
      onContinueMission={(mission) => router.push(missionDetailPath(mission.mission_id))}
      onViewMemory={() => router.push("/memory")}
    />
  );
}
