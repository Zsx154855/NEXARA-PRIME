"use client";

import { useRouter } from "next/navigation";
import { ConversationScreen } from "@/components/screens/ConversationScreen";
import { useRuntimeData } from "@/lib/runtime-context";
import { missionDetailPath } from "@/lib/navigation";

export default function ConversationPage() {
  const router = useRouter();
  const { api } = useRuntimeData();

  return (
    <ConversationScreen
      api={api}
      onMissionSelect={(missionId) => router.push(missionDetailPath(missionId))}
      onViewApprovals={() => router.push("/trust")}
    />
  );
}
