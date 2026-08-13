"use client";

import { EmptyState } from "@/components/ui/EmptyState";

/**
 * 设置 — 工具与连接器（批次 4 实现：connectors registry 只读投影；
 * 连接动作标 CONNECTOR_REQUIRED）
 */
export default function SettingsToolsPage() {
  return (
    <EmptyState
      title="工具与连接器"
      description="连接器状态只读投影（browser / git / messenger 等 adapter），未连接的 adapter 如实显示「未连接」；连接动作标 CONNECTOR_REQUIRED。此视图将在后续批次接入 connectors registry。"
    />
  );
}
