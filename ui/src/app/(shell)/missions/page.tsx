"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { useRouter } from "next/navigation";
import { MissionCreator } from "@/components/screens/MissionCreator";
import { MissionWorkspace } from "@/components/screens/MissionWorkspace";
import { useRuntimeData } from "@/lib/runtime-context";
import { missionDetailPath } from "@/lib/navigation";

function MissionsRoute() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { api, overview } = useRuntimeData();
  const missionId = searchParams.get("id");

  if (missionId) {
    return (
      <MissionWorkspace
        api={api}
        missionId={missionId}
        onBack={() => router.push("/missions")}
      />
    );
  }

  return (
    <MissionCreator
      api={api}
      onCreated={() => router.push("/missions")}
      overview={overview}
      onMissionSelect={(missionId) => router.push(missionDetailPath(missionId))}
    />
  );
}

export default function MissionsPage() {
  return (
    <Suspense fallback={null}>
      <MissionsRoute />
    </Suspense>
  );
}
