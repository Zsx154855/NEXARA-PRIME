"use client";

import type { NexaraAPI } from "@/lib/api";
import type { RuntimeOverview } from "@/types";
import { cn } from "@/lib/utils";
import {
  Activity,
  Server,
  ShieldCheck,
  ShieldAlert,
  Database,
  FileSearch,
  Cpu,
  Code2,
  CheckCircle2,
  XCircle,
  RefreshCw,
  Box,
  HardDrive,
  Globe,
  Hash,
  User,
  Zap,
  Terminal,
} from "lucide-react";

interface RuntimeHealthProps {
  api: NexaraAPI;
  overview: RuntimeOverview | null;
}

function HealthBadge({ healthy, label }: { healthy: boolean; label?: string }) {
  return (
    <span className={cn(
      "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[11px] font-medium border",
      healthy
        ? "bg-moss-green/10 text-moss-green border-moss-green/20"
        : "bg-warm-red/10 text-warm-red border-warm-red/20"
    )}>
      {healthy ? (
        <CheckCircle2 className="h-3 w-3" />
      ) : (
        <XCircle className="h-3 w-3" />
      )}
      {label ?? (healthy ? "正常" : "异常")}
    </span>
  );
}

function Section({
  title,
  icon: Icon,
  iconColor,
  children,
}: {
  title: string;
  icon: typeof Activity;
  iconColor: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-taupe bg-ivory overflow-hidden">
      <div className="flex items-center gap-2 border-b border-taupe bg-mist-gray px-4 py-2.5">
        <Icon className={cn("h-4 w-4", iconColor)} />
        <h3 className="text-xs font-medium uppercase tracking-wider text-graphite">
          {title}
        </h3>
      </div>
      <div className="p-4">
        {children}
      </div>
    </div>
  );
}

function StatRow({
  label,
  value,
  valueColor,
  icon: Icon,
}: {
  label: string;
  value: React.ReactNode;
  valueColor?: string;
  icon?: typeof Activity;
}) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-taupe/30 last:border-0">
      <div className="flex items-center gap-2">
        {Icon && <Icon className="h-3.5 w-3.5 text-stone/40" />}
        <span className="text-xs text-stone/60">{label}</span>
      </div>
      <div className={cn("text-xs font-medium text-graphite", valueColor)}>
        {value}
      </div>
    </div>
  );
}

function Skeleton() {
  return (
    <div className="animate-pulse-soft space-y-4">
      <div className="h-8 w-48 rounded bg-taupe/50" />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-40 rounded-xl bg-taupe/30" />
        ))}
      </div>
    </div>
  );
}

export function RuntimeHealth({ api: _api, overview }: RuntimeHealthProps) {
  const system = overview?.system;
  const healthStatus = system?.healthy;

  // Loading state
  if (!overview) {
    return <Skeleton />;
  }

  return (
    <div className="animate-fade-in space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-mist-gray text-moss-green">
            <Activity className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-graphite">系统健康</h1>
            <p className="text-xs text-stone/60">
              NEXARA PRIME 运行时状态概览
            </p>
          </div>
        </div>
        <HealthBadge healthy={healthStatus ?? false} label={healthStatus ? "系统健康" : "系统异常"} />
      </div>

      {/* System grid */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Provider */}
        <Section title="提供方" icon={Server} iconColor="text-champagne">
          <StatRow
            label="Provider"
            value={system?.mode ?? "—"}
            icon={Cpu}
          />
          <StatRow
            label="确认状态"
            value={<HealthBadge healthy={!system?.mock_default} label={system?.mock_default ? "Mock 默认" : "已确认"} />}
          />
          <StatRow
            label="人工控制"
            value={system?.human_control ? "启用" : "关闭"}
            valueColor={system?.human_control ? "text-moss-green" : "text-stone/60"}
            icon={User}
          />
          <StatRow
            label="运行模式"
            value={system?.name ?? "—"}
            icon={Code2}
          />
        </Section>

        {/* Safe Mode & Recovery */}
        <Section title="安全模式与恢复" icon={ShieldAlert} iconColor="text-amber">
          <StatRow
            label="安全模式"
            value={system?.mock_default ? (
              <span className="flex items-center gap-1.5 text-amber">
                <ShieldAlert className="h-3.5 w-3.5" />
                已启用（Mock Provider）
              </span>
            ) : (
              <span className="flex items-center gap-1.5 text-moss-green">
                <ShieldCheck className="h-3.5 w-3.5" />
                已关闭
              </span>
            )}
          />
          <StatRow
            label="NSEC 状态"
            value={
              <span className="flex items-center gap-1.5 text-moss-green">
                <CheckCircle2 className="h-3.5 w-3.5" />
                已治理
              </span>
            }
          />
          <StatRow
            label="恢复检查"
            value={
              <span className="flex items-center gap-1.5 text-stone/60">
                <RefreshCw className="h-3.5 w-3.5" />
                可用
              </span>
            }
          />
        </Section>

        {/* Evidence Store */}
        <Section title="证据存储" icon={FileSearch} iconColor="text-moss-green">
          <StatRow
            label="证据数量"
            value={overview.evidence.length}
            icon={FileSearch}
          />
          <StatRow
            label="最新证据"
            value={overview.evidence.length > 0
              ? overview.evidence[overview.evidence.length - 1]?.evidence_id?.slice(0, 16) + "…"
              : "无"
            }
            valueColor={overview.evidence.length > 0 ? "text-graphite" : "text-stone/40"}
            icon={Hash}
          />
          <StatRow
            label="证据验证"
            value={
              overview.evidence.filter((e) => e.verification_status === "verified").length > 0
                ? <HealthBadge healthy={true} label="已验证" />
                : <HealthBadge healthy={false} label="未验证" />
            }
          />
        </Section>

        {/* Memory Store */}
        <Section title="内存存储" icon={Database} iconColor="text-amber">
          <StatRow
            label="内存记录"
            value="—"  // Not directly in overview
            icon={Database}
          />
          <StatRow
            label="任务内存关联"
            value={overview.missions.filter((m) => m.memory_patch_status === "patched").length > 0
              ? `${overview.missions.filter((m) => m.memory_patch_status === "patched").length} 个任务已应用`
              : "暂无"
            }
            valueColor="text-graphite"
            icon={Box}
          />
        </Section>

        {/* API Status */}
        <Section title="API 状态" icon={Globe} iconColor="text-champagne">
          <StatRow
            label="REST API"
            value={<HealthBadge healthy={true} label="可用" />}
            icon={Zap}
          />
          <StatRow
            label="事件系统"
            value={overview.missions.length > 0
              ? <HealthBadge healthy={true} />
              : <span className="text-stone/40">无数据</span>
            }
            icon={Activity}
          />
          <StatRow
            label="工具调用"
            value={overview.tools?.length > 0
              ? `${overview.tools.length} 次调用`
              : "无"
            }
            icon={Terminal}
          />
        </Section>

        {/* Version */}
        <Section title="版本信息" icon={Code2} iconColor="text-champagne">
          <StatRow
            label="Runtime 名称"
            value={system?.name ?? "NEXARA PRIME"}
            icon={Server}
          />
          <StatRow
            label="数据库"
            value={overview.missions.length > 0 ? "SQLite (持久化)" : "—"}
            icon={HardDrive}
          />
          <StatRow
            label="Adapter 状态"
            value={
              system?.adapters && Object.keys(system.adapters).length > 0
                ? Object.entries(system.adapters).map(([k, v]) => (
                    <span key={k} className="mr-2 inline-flex items-center gap-1">
                      <span className={cn(
                        "h-1.5 w-1.5 rounded-full",
                        v ? "bg-moss-green" : "bg-warm-red"
                      )} />
                      {k}
                    </span>
                  ))
                : <span className="text-stone/40">无</span>
            }
          />
        </Section>
      </div>

      {/* Recovery section */}
      {overview.recovery && Object.keys(overview.recovery).length > 0 && (
        <div className="rounded-xl border border-taupe bg-ivory p-4">
          <h3 className="mb-3 flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-stone/70">
            <Activity className="h-3.5 w-3.5 text-champagne" />
            恢复状态
          </h3>
          <pre className="max-h-40 overflow-auto rounded-lg bg-mist-gray p-3 text-[11px] font-mono text-graphite leading-relaxed">
            {JSON.stringify(overview.recovery, null, 2)}
          </pre>
        </div>
      )}

      {/* Mission status summary */}
      <div className="rounded-xl border border-taupe bg-ivory p-4">
        <h3 className="mb-3 flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-stone/70">
          <Activity className="h-3.5 w-3.5 text-champagne" />
          任务状态总览
        </h3>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <StatusCount label="活跃" count={overview.missions.filter((m) => m.state !== "Completed" && m.state !== "Failed" && m.state !== "RolledBack").length} color="text-champagne" />
          <StatusCount label="已完成" count={overview.missions.filter((m) => m.state === "Completed").length} color="text-moss-green" />
          <StatusCount label="失败" count={overview.missions.filter((m) => m.state === "Failed").length} color="text-warm-red" />
          <StatusCount label="待审批" count={overview.approvals.filter((a) => a.status === "pending").length} color="text-amber" />
          <StatusCount label="暂停" count={overview.missions.filter((m) => m.paused).length} color="text-amber" />
          <StatusCount label="总计" count={overview.missions.length} color="text-graphite" />
        </div>
      </div>
    </div>
  );
}

function StatusCount({ label, count, color }: { label: string; count: number; color: string }) {
  return (
    <div className="rounded-lg border border-taupe bg-mist-gray p-3 text-center">
      <div className={cn("text-lg font-bold", color)}>{count}</div>
      <div className="text-[10px] uppercase tracking-wider text-stone/50">{label}</div>
    </div>
  );
}
