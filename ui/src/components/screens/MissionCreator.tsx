// MissionCreator 容器：使命列表（默认）↔ 三步创建向导。
// 依赖注入与回调签名保持不变（missions/page.tsx 与 missions/new/page.tsx 兼容）。

"use client";

import { useState } from "react";
import type { NexaraAPI } from "@/lib/api";
import type { RuntimeOverview } from "@/types";
import { MissionList } from "./missionCreator/MissionList";
import { MissionWizard } from "./missionCreator/MissionWizard";

interface MissionCreatorProps {
  api: NexaraAPI;
  onCreated: () => void;
  overview?: RuntimeOverview | null;
  onMissionSelect?: (missionId: string) => void;
}

export function MissionCreator({ api, onCreated, overview, onMissionSelect }: MissionCreatorProps) {
  const [showForm, setShowForm] = useState(false);

  const closeWizard = () => {
    setShowForm(false);
    onCreated();
  };

  if (showForm) {
    return <MissionWizard api={api} onClose={closeWizard} />;
  }

  return (
    <MissionList
      missions={overview?.missions ?? []}
      onSelect={(missionId) => onMissionSelect?.(missionId)}
      onCreate={() => setShowForm(true)}
    />
  );
}
