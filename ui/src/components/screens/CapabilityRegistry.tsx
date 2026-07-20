"use client";

import type { RuntimeOverview, Capability } from "@/types";
import { cn } from "@/lib/utils";
import {
  Puzzle,
  Wrench,
  Cpu,
  Database,
  Shield,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Activity,
} from "lucide-react";

interface CapabilityRegistryProps {
  api: unknown;
  overview: RuntimeOverview | null;
}

const TYPE_CONFIG: Record<
  string,
  { icon: typeof Puzzle; label: string; color: string }
> = {
  skill: { icon: Puzzle, label: "技能", color: "text-accent" },
  tool: { icon: Wrench, label: "工具", color: "text-info" },
  model: { icon: Cpu, label: "模型", color: "text-success" },
  memory: { icon: Database, label: "记忆", color: "text-warning" },
  policy: { icon: Shield, label: "策略", color: "text-error" },
};

function CapabilityCard({ cap }: { cap: Capability }) {
  const config = TYPE_CONFIG[cap.capability_type] ?? {
    icon: Activity,
    label: cap.capability_type,
    color: "text-text-tertiary",
  };
  const Icon = config.icon;

  return (
    <div className="surface-card flex items-start gap-4 p-4 transition-all hover:shadow-md">
      {/* Type icon */}
      <div
        className={cn(
          "flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg",
          cap.enabled ? "bg-accent-subtle" : "bg-bg-secondary"
        )}
      >
        <Icon className={cn("h-5 w-5", cap.enabled ? config.color : "text-text-tertiary")} />
      </div>

      {/* Content */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-text-primary">
            {cap.name}
          </span>
          <span className="badge badge-neutral text-[10px]">
            {config.label}
          </span>
          {cap.enabled ? (
            <span className="badge badge-success text-[10px]">
              <CheckCircle2 className="mr-0.5 h-2.5 w-2.5" />
              已启用
            </span>
          ) : (
            <span className="badge badge-error text-[10px]">
              <XCircle className="mr-0.5 h-2.5 w-2.5" />
              已禁用
            </span>
          )}
        </div>
        <p className="mt-1 text-xs leading-relaxed text-text-secondary">
          {cap.description}
        </p>
        <div className="mt-2 flex items-center gap-3 text-[11px] text-text-tertiary">
          <span>
            ID：<code className="font-mono">{cap.capability_id}</code>
          </span>
          <span
            className={cn(
              "inline-flex items-center gap-0.5",
              cap.risk_level === "R0"
                ? "text-success"
                : cap.risk_level === "R1" || cap.risk_level === "R2"
                  ? "text-warning"
                  : "text-error"
            )}
          >
            <AlertTriangle className="h-3 w-3" />
            {cap.risk_level}
          </span>
        </div>
      </div>
    </div>
  );
}

export function CapabilityRegistry({ api: _api, overview }: CapabilityRegistryProps) {
  const capabilities = overview?.capabilities ?? [];
  const loading = !overview;

  // Loading state
  if (loading) {
    return (
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="surface-card animate-pulse p-4">
            <div className="skeleton mb-3 h-10 w-10 rounded-lg" />
            <div className="skeleton mb-2 h-4 w-2/3" />
            <div className="skeleton h-3 w-full" />
          </div>
        ))}
      </div>
    );
  }

  // Empty state
  if (capabilities.length === 0) {
    return (
      <div className="surface-card flex flex-col items-center gap-3 py-16 text-center">
        <Puzzle className="h-12 w-12 text-text-tertiary" />
        <div className="text-base font-medium text-text-primary">暂无已注册能力</div>
        <div className="text-sm text-text-tertiary">
          运行时未报告任何能力或工具注册信息
        </div>
      </div>
    );
  }

  const byType = capabilities.reduce<Record<string, Capability[]>>(
    (acc, cap) => {
      (acc[cap.capability_type] ??= []).push(cap);
      return acc;
    },
    {}
  );

  const typeOrder = ["skill", "tool", "model", "memory", "policy"];

  // Grouped display
  return (
    <div className="space-y-6">
      {/* Summary bar */}
      <div className="surface-card flex items-center gap-6 px-4 py-3">
        {typeOrder.map((type) => {
          const group = byType[type] ?? [];
          const config = TYPE_CONFIG[type];
          const Icon = config?.icon ?? Activity;
          return (
            <div key={type} className="flex items-center gap-2">
              <Icon className={cn("h-4 w-4", config?.color ?? "text-text-tertiary")} />
              <span className="text-sm text-text-secondary">
                {config?.label ?? type}
              </span>
              <span className="text-sm font-medium text-text-primary">
                {group.length}
              </span>
            </div>
          );
        })}
      </div>

      {/* By type */}
      <div className="space-y-4">
        {typeOrder
          .filter((type) => (byType[type] ?? []).length > 0)
          .map((type) => {
            const group = byType[type] ?? [];
            const config = TYPE_CONFIG[type];
            const Icon = config?.icon ?? Activity;
            return (
              <section key={type}>
                <div className="mb-2 flex items-center gap-2">
                  <Icon className={cn("h-4 w-4", config?.color)} />
                  <h2 className="text-sm font-medium text-text-primary">
                    {config?.label ?? type}
                  </h2>
                  <span className="text-xs text-text-tertiary">
                    {group.length} 项
                  </span>
                </div>
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  {group.map((cap) => (
                    <CapabilityCard key={cap.capability_id} cap={cap} />
                  ))}
                </div>
              </section>
            );
          })}
      </div>
    </div>
  );
}
