"use client";

import { EmptyState } from "@/components/ui/EmptyState";

/**
 * 设置 — 只读镜像（批次 4 实现）。
 * env 驱动（NEXARA_MODEL_PROVIDER 等），运行时无可写项，
 * 变更方式 = 改 env / 重启。
 */
export default function SettingsPage() {
  return (
    <EmptyState
      title="设置"
      description="配置为环境变量驱动（NEXARA_MODEL_PROVIDER / NEXARA_DB_PATH 等），运行时只读。此视图将在后续批次以只读镜像呈现，变更方式为修改 env 后重启。当前状态：尚未接入。"
    />
  );
}
