"use client";

import { useState, useEffect, useCallback } from "react";
import { NexaraAPI } from "@/lib/api";
import { RuntimeOverview, RuntimeStats } from "@/types";
import { Sidebar } from "@/components/Sidebar";
import { TopBar } from "@/components/TopBar";
import { Overview } from "@/components/screens/Overview";
import { MissionCreator } from "@/components/screens/MissionCreator";
import { MissionWorkspace } from "@/components/screens/MissionWorkspace";
import { ApprovalCenter } from "@/components/screens/ApprovalCenter";
import { EvidenceViewer } from "@/components/screens/EvidenceViewer";
import { RuntimeHealth } from "@/components/screens/RuntimeHealth";

export type Screen =
  | "dashboard"
  | "missions"
  | "mission-workspace"
  | "evidence"
  | "governance"
  | "runtime-health";

export default function DashboardShell() {
  const [screen, setScreen] = useState<Screen>("dashboard");
  const [overview, setOverview] = useState<RuntimeOverview | null>(null);
  const [stats, setStats] = useState<RuntimeStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedMissionId, setSelectedMissionId] = useState<string | null>(null);
  const [missionCreated, setMissionCreated] = useState(0);

  const api = new NexaraAPI();

  const loadData = useCallback(async () => {
    try {
      const [ov, st] = await Promise.all([api.getOverview(), api.getStats()]);
      setOverview(ov);
      setStats(st);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "无法连接到 NEXARA Runtime");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, [loadData, missionCreated]);

  const handleMissionSelect = (missionId: string) => {
    setSelectedMissionId(missionId);
    setScreen("mission-workspace");
  };

  const handleMissionCreated = () => {
    setMissionCreated((c) => c + 1);
    setScreen("missions");
  };

  const handleCreateMission = () => {
    setScreen("missions");
  };

  return (
    <div className="flex h-screen overflow-hidden bg-ivory text-graphite">
      <Sidebar screen={screen} onNavigate={setScreen} onMissionSelect={handleMissionSelect} overview={overview} />

      <div className="flex flex-1 flex-col overflow-hidden">
        <TopBar
          screen={screen}
          overview={overview}
          loading={loading}
          error={error}
          onRefresh={loadData}
        />

        <main className="flex-1 overflow-auto p-6">
          {screen === "dashboard" && (
            <Overview
              overview={overview}
              stats={stats}
              loading={loading}
              error={error}
              onMissionSelect={handleMissionSelect}
              onCreateMission={handleCreateMission}
            />
          )}
          {screen === "missions" && (
            <MissionCreator api={api} onCreated={handleMissionCreated} overview={overview} onMissionSelect={handleMissionSelect} />
          )}
          {screen === "mission-workspace" && selectedMissionId && (
            <MissionWorkspace
              api={api}
              missionId={selectedMissionId}
              onBack={() => setScreen("missions")}
            />
          )}
          {screen === "evidence" && (
            <EvidenceViewer api={api} overview={overview} />
          )}
          {screen === "governance" && (
            <ApprovalCenter api={api} />
          )}
          {screen === "runtime-health" && (
            <RuntimeHealth api={api} overview={overview} stats={stats} />
          )}
        </main>
      </div>
    </div>
  );
}
