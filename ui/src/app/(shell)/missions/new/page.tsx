"use client";

import { useRouter } from "next/navigation";
import { MissionCreator } from "@/components/screens/MissionCreator";
import { useRuntimeData } from "@/lib/runtime-context";

export default function NewMissionPage() {
  const router = useRouter();
  const { api, overview } = useRuntimeData();

  return (
    <MissionCreator
      api={api}
      onCreated={() => router.push("/missions")}
      overview={overview}
      onMissionSelect={() => router.push("/missions")}
    />
  );
}
