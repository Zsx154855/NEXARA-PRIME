"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { NavSidebar } from "@/components/navigation/NavSidebar";
import { MobileNav } from "@/components/navigation/MobileNav";
import { TopBar } from "@/components/layout/TopBar";
import { CommandPalette } from "@/components/CommandPalette";
import { RuntimeDataProvider, useRuntimeData } from "@/lib/runtime-context";
import { missionDetailPath } from "@/lib/navigation";

/**
 * NEXARA 应用壳 — 六区导航 + 顶栏 + 内容区 + ⌘K。
 * 数据由 RuntimeDataProvider 提供（10s 轮询，对用户不可见）。
 */
function ShellContent({ children }: { children: React.ReactNode }) {
  const { overview, memories } = useRuntimeData();
  const [cmdPaletteOpen, setCmdPaletteOpen] = useState(false);
  const router = useRouter();

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setCmdPaletteOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const missions = overview?.missions ?? [];
  const hasPendingApprovals =
    overview?.approvals?.some((a) => a.status === "pending") ?? false;

  const handleMissionSelect = (missionId: string) => {
    router.push(missionDetailPath(missionId));
  };

  const handleContinueMission = () => {
    const active = missions.find(
      (m) => !["Completed", "Failed", "RolledBack"].includes(m.state),
    );
    if (active) handleMissionSelect(active.mission_id);
  };

  return (
    <div className="flex h-screen overflow-hidden bg-surface-base text-text-primary">
      <NavSidebar />

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <TopBar onOpenCommandPalette={() => setCmdPaletteOpen(true)} />
        <main className="flex-1 overflow-auto p-4 pb-20 sm:p-6 lg:pb-6">{children}</main>
      </div>

      <MobileNav />

      <CommandPalette
        open={cmdPaletteOpen}
        onClose={() => setCmdPaletteOpen(false)}
        missions={missions}
        memories={memories}
        onMissionSelect={handleMissionSelect}
        onCreateMission={() => router.push("/missions/new")}
        onContinueMission={handleContinueMission}
        onViewMemory={() => router.push("/memory")}
        onViewRuntime={() => router.push("/")}
        onViewEvidence={() => router.push("/trust/evidence")}
      />

      {/* aria-live 区域：审批到达播报（读屏器） */}
      <div aria-live="polite" className="sr-only">
        {hasPendingApprovals ? "有待审批项等待你的决定" : ""}
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <RuntimeDataProvider>
      <ShellContent>{children}</ShellContent>
    </RuntimeDataProvider>
  );
}
