"use client";

import { Status } from "@/components/ui/Status";
import { Badge } from "@/components/ui/Badge";
import { LoadingState } from "@/components/ui/LoadingState";
import { PermissionState } from "@/components/ui/PermissionState";
import { useRuntimeData } from "@/lib/runtime-context";

/**
 * 设置 — 工具与连接器（只读投影）。
 * adapters 布尔来自 /api/runtime/overview 真实字段；
 * 连接动作标 CONNECTOR_REQUIRED（后端无对应端点），不做假按钮。
 */
const ADAPTER_LABELS: Record<string, string> = {
  browser: "浏览器",
  computer_use: "计算机操作",
  git: "Git 仓库",
  messenger: "消息通道",
  deployment: "部署",
  rag: "知识检索（RAG）",
  repair: "修复循环",
  program_loop: "程序循环",
};

export default function SettingsToolsPage() {
  const { overview, loading } = useRuntimeData();

  if (loading && overview === null) {
    return <LoadingState label="正在读取连接器状态…" />;
  }

  const adapters = overview?.system.adapters ?? {};
  const adapterEntries =
    Object.keys(adapters).length > 0
      ? Object.entries(adapters)
      : null;

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4 px-2 py-4">
      <section aria-labelledby="tools-heading">
        <h2 id="tools-heading" className="mb-1 text-sm font-semibold text-text-primary">
          工具与连接器
        </h2>
        <p className="mb-3 text-xs text-text-secondary">
          连接器状态为只读投影；连接与配置动作标 CONNECTOR_REQUIRED（后端无对应端点）。
        </p>
        <PermissionState
          requirement="连接器配置"
          reason="连接/启停连接器需要 connector.configure 权限，该权限列入 Agent 永久禁用清单且后端无对应端点。"
          marker="CONNECTOR_REQUIRED"
          className="mb-4"
        />
        {adapterEntries === null ? (
          <p className="text-sm text-text-secondary">未提供连接器状态（运行时未报告）。</p>
        ) : (
          <ul className="flex flex-col divide-y divide-border-subtle" aria-label="连接器列表">
            {adapterEntries.map(([key, connected]) => (
              <li key={key} className="flex items-center justify-between gap-4 py-3">
                <span className="text-sm text-text-primary">
                  {ADAPTER_LABELS[key] ?? key}
                </span>
                <span className="flex items-center gap-2">
                  {connected ? (
                    <Status tone="success" label="已连接" />
                  ) : (
                    <>
                      <Status tone="neutral" label="未连接" />
                      <Badge tone="neutral">CONNECTOR_REQUIRED</Badge>
                    </>
                  )}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
