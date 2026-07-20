"use client";

import { useState, useEffect, useCallback } from "react";
import { NexaraAPI } from "@/lib/api";
import { RuntimeOverview } from "@/types";
import { Sidebar } from "@/components/Sidebar";
import { TopBar } from "@/components/TopBar";
import { Overview } from "@/components/screens/Overview";
import { MissionCreator } from "@/components/screens/MissionCreator";
import { MissionWorkspace } from "@/components/screens/MissionWorkspace";
import { ApprovalCenter } from "@/components/screens/ApprovalCenter";
import { EvidenceViewer } from "@/components/screens/EvidenceViewer";
import { CapabilityRegistry } from "@/components/screens/CapabilityRegistry";
import { RuntimeHealth } from "@/components/screens/RuntimeHealth";

export type Screen =
  | "overview"
  | "mission-creator"
  | "mission-workspace"
  | "approvals"
  | "evidence"
  | "capabilities"
  | "health";

export default function DashboardShell() {
  const [screen, setScreen] = useState<Screen>("overview");
  const [overview, setOverview] = useState<RuntimeOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedMissionId, setSelectedMissionId] = useState<string | null>(null);
  const [missionCreated, setMissionCreated] = useState(0);

  const api = new NexaraAPI();

  const loadOverview = useCallback(async () => {
    try {
      const data = await api.getOverview();
      setOverview(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "无法连接到 NEXARA Runtime");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadOverview();
    const interval = setInterval(loadOverview, 10000);
    return () => clearInterval(interval);
  }, [loadOverview, missionCreated]);

  const handleMissionSelect = (missionId: string) => {
    setSelectedMissionId(missionId);
    setScreen("mission-workspace");
  };

  const handleMissionCreated = () => {
    setMissionCreated((c) => c + 1);
    setScreen("overview");
  };

  return (
    <div className="flex h-screen overflow-hidden bg-ivory text-graphite">
      {/* Left Sidebar Navigation */}
      <Sidebar screen={screen} onNavigate={setScreen} overview={overview} />

      {/* Main Content Area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <TopBar
          screen={screen}
          overview={overview}
          loading={loading}
          error={error}
          onRefresh={loadOverview}
        />

        <main className="flex-1 overflow-auto p-6">
          {screen === "overview" && (
            <Overview
              overview={overview}
              loading={loading}
              error={error}
              onMissionSelect={handleMissionSelect}
            />
          )}
          {screen === "mission-creator" && (
            <MissionCreator api={api} onCreated={handleMissionCreated} />
          )}
          {screen === "mission-workspace" && selectedMissionId && (
            <MissionWorkspace
              api={api}
              missionId={selectedMissionId}
              onBack={() => setScreen("overview")}
            />
          )}
          {screen === "approvals" && (
            <ApprovalCenter api={api} />
          )}
          {screen === "evidence" && (
            <EvidenceViewer api={api} overview={overview} />
          )}
          {screen === "capabilities" && (
            <CapabilityRegistry api={api} overview={overview} />
          )}
          {screen === "health" && (
            <RuntimeHealth api={api} overview={overview} />
          )}
        </main>
      </div>
    </div>
  );
}
