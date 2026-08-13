"use client";

import { useState, useEffect, useCallback } from "react";
import { NexaraAPI, configureApi } from "@/lib/api";
import type { RuntimeOverview, RuntimeStats, MissionSnapshot, MemoryRecord, MemoryStats } from "@/types";
import { Sidebar } from "@/components/Sidebar";
import { TopBar } from "@/components/TopBar";
import { Overview } from "@/components/screens/Overview";
import { MissionCreator } from "@/components/screens/MissionCreator";
import { MissionWorkspace } from "@/components/screens/MissionWorkspace";
import { ApprovalCenter } from "@/components/screens/ApprovalCenter";
import { EvidenceViewer } from "@/components/screens/EvidenceViewer";
import { RuntimeHealth } from "@/components/screens/RuntimeHealth";
import { ConversationScreen } from "@/components/screens/ConversationScreen";
import { CommandPalette } from "@/components/CommandPalette";

export type Screen =
  | "dashboard"
  | "missions"
  | "mission-workspace"
  | "conversation"
  | "evidence"
  | "governance"
  | "runtime-health"
  | "memory";

const api = new NexaraAPI();

export default function DashboardShell() {
  // Client-side only: configure API base URL for dev (different port than UI).
  // Module-level code runs during SSR where window is undefined —
  // useEffect guarantees execution only in the browser.
  useEffect(() => {
    configureApi({
      baseUrl: window.location.hostname === "localhost"
        ? "http://127.0.0.1:8765"
        : "",
    });
  }, []);

  const [screen, setScreen] = useState<Screen>("dashboard");
  const [overview, setOverview] = useState<RuntimeOverview | null>(null);
  const [stats, setStats] = useState<RuntimeStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedMissionId, setSelectedMissionId] = useState<string | null>(null);
  const [missionCreated, setMissionCreated] = useState(0);
  const [cmdPaletteOpen, setCmdPaletteOpen] = useState(false);
  const [memories, setMemories] = useState<MemoryRecord[]>([]);
  const [memoryStats, setMemoryStats] = useState<MemoryStats | null>(null);

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

  const loadMemories = useCallback(async () => {
    try {
      const [mems, memStats] = await Promise.all([
        api.getMemory(),
        api.getMemoryStats(),
      ]);
      setMemories(mems);
      setMemoryStats(memStats);
    } catch {
      // Memory fetch is best-effort; don't surface errors globally
    }
  }, []);

  useEffect(() => {
    loadData();
    loadMemories();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, [loadData, loadMemories, missionCreated]);

  // ⌘K handler
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setCmdPaletteOpen((prev) => !prev);
        loadMemories(); // refresh memories when opening palette
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [loadMemories]);

  const handleMissionSelect = (missionId: string) => {
    setSelectedMissionId(missionId);
    setScreen("mission-workspace");
  };

  const handleMissionCreated = () => {
    setMissionCreated((c) => c + 1);
    setScreen("missions");
  };

  const handleCreateMission = () => setScreen("missions");

  const handleContinueMission = (mission: MissionSnapshot) => {
    setSelectedMissionId(mission.mission_id);
    setScreen("mission-workspace");
  };

  const handleViewMemory = () => setScreen("memory");

  const missions = overview?.missions ?? [];

  return (
    <div className="flex h-screen overflow-hidden bg-surface-base text-text-primary">
      <Sidebar
        screen={screen}
        onNavigate={setScreen}
        onMissionSelect={handleMissionSelect}
        overview={overview}
      />

      <div className="flex flex-1 flex-col overflow-hidden">
        <TopBar
          screen={screen}
          overview={overview}
          loading={loading}
          error={error}
          onRefresh={loadData}
          onOpenCommandPalette={() => setCmdPaletteOpen(true)}
        />

        <main className="flex-1 overflow-auto p-4 sm:p-6">
          {screen === "dashboard" && (
            <Overview
              overview={overview}
              stats={stats}
              memoryStats={memoryStats}
              loading={loading}
              error={error}
              onMissionSelect={handleMissionSelect}
              onCreateMission={handleCreateMission}
              onContinueMission={handleContinueMission}
              onViewMemory={handleViewMemory}
            />
          )}
          {screen === "missions" && (
            <MissionCreator
              api={api}
              onCreated={handleMissionCreated}
              overview={overview}
              onMissionSelect={handleMissionSelect}
            />
          )}
          {screen === "mission-workspace" && selectedMissionId && (
            <MissionWorkspace
              api={api}
              missionId={selectedMissionId}
              onBack={() => setScreen("missions")}
            />
          )}
          {screen === "conversation" && (
            <ConversationScreen
              api={api}
              onMissionSelect={handleMissionSelect}
              onViewApprovals={() => setScreen("governance")}
            />
          )}
          {screen === "evidence" && (
            <EvidenceViewer api={api} overview={overview} />
          )}
          {screen === "governance" && <ApprovalCenter api={api} />}
          {screen === "runtime-health" && (
            <RuntimeHealth api={api} overview={overview} stats={stats} />
          )}
          {screen === "memory" && (
            <EvidenceViewer api={api} overview={overview} />
          )}
        </main>
      </div>

      {/* Command Palette */}
      <CommandPalette
        open={cmdPaletteOpen}
        onClose={() => setCmdPaletteOpen(false)}
        missions={missions}
        memories={memories}
        onMissionSelect={handleMissionSelect}
        onCreateMission={handleCreateMission}
        onContinueMission={() => {
          const active = missions.find(
            (m) => !["Completed", "Failed", "RolledBack"].includes(m.state),
          );
          if (active) handleContinueMission(active);
        }}
        onViewMemory={handleViewMemory}
        onViewRuntime={() => setScreen("runtime-health")}
        onViewEvidence={() => setScreen("evidence")}
      />
    </div>
  );
}
