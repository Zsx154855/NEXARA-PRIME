// 生成中的唯一允许动画 = LoadingState 细线进度（禁 spinner / pulse）。

import { LoadingState } from "@/components/ui/LoadingState";

interface ProgressViewProps {
  phaseLabel: string;
  missionId: string | null;
}

export function ProgressView({ phaseLabel, missionId }: ProgressViewProps) {
  return (
    <div className="flex flex-col items-center gap-5 py-16">
      <LoadingState label={phaseLabel} className="w-full max-w-md" />
      <p className="text-xs text-text-secondary">
        任务 ID：{missionId ? `${missionId.slice(0, 16)}…` : "—"}
      </p>
    </div>
  );
}
