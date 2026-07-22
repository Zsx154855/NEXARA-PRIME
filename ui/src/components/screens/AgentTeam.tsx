"use client";

import { useState, useEffect } from "react";
import type { NexaraAPI } from "@/lib/api";
import type { RuntimeOverview } from "@/types";
import { Bot, Loader2, WifiOff, Cpu, Activity, Zap } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  api: NexaraAPI;
  overview: RuntimeOverview | null;
}

export function AgentTeam({ api: _api, overview }: Props) {
  const [adaptiveStatus, setAdaptiveStatus] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const status = await _api.getAdaptiveStatus();
        if (!cancelled) setAdaptiveStatus(status);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "加载失败");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [_api]);

  // Derive from overview real agent data
  const systemAdapters = overview?.system?.adapters ?? {};
  const hasActiveAgents = overview && Object.values(systemAdapters).some(Boolean);

  return (
    <div className="animate-fade-in space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-stone/70">多智能体团队</h2>
          <p className="mt-1 text-xs text-stone/60">当前激活的 Agent、角色与路由</p>
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex flex-col items-center gap-4 py-16">
          <Loader2 className="h-8 w-8 animate-spin text-champagne" />
          <p className="text-sm text-stone">正在查询 Agent 状态…</p>
        </div>
      )}

      {/* Error */}
      {error && !loading && (
        <div className="flex flex-col items-center gap-3 rounded-xl border border-warm-red/20 bg-warm-red/5 py-12 text-center">
          <WifiOff className="h-8 w-8 text-warm-red" />
          <p className="text-sm text-warm-red">{error}</p>
        </div>
      )}

      {/* Empty state — no active agents */}
      {!loading && !error && !hasActiveAgents && !adaptiveStatus?.missions?.length && (
        <div className="flex flex-col items-center gap-4 rounded-xl border border-taupe bg-ivory py-16 text-center">
          <Bot className="h-12 w-12 text-stone/30" />
          <div>
            <p className="text-sm font-medium text-graphite">当前没有活动的 Agent</p>
            <p className="mt-1 max-w-sm text-xs text-stone/60">
              当任务进入 Execution 阶段后，Runtime 将根据任务需求和能力注册表自动分配 Agent。
              你可以通过 Adaptive API 查看详细的路由和调度信息。
            </p>
          </div>
        </div>
      )}

      {/* Real agent data from overview adapters */}
      {!loading && hasActiveAgents && (
        <div className="space-y-4">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-stone/60">系统适配器</h3>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {Object.entries(systemAdapters).map(([name, active]) => (
              <div key={name} className={cn(
                "rounded-xl border p-4",
                active ? "border-moss-green/20 bg-moss-green/5" : "border-taupe bg-ivory opacity-60"
              )}>
                <div className="flex items-center gap-3">
                  <div className={cn(
                    "flex h-8 w-8 items-center justify-center rounded-lg",
                    active ? "bg-moss-green/10 text-moss-green" : "bg-taupe/20 text-stone/40"
                  )}>
                    {name === "browser" ? <Activity className="h-4 w-4"/> :
                     name === "computer_use" ? <Cpu className="h-4 w-4"/> :
                     name === "git" ? <Zap className="h-4 w-4"/> :
                     <Bot className="h-4 w-4"/>}
                  </div>
                  <div>
                    <div className="text-sm font-medium text-graphite capitalize">{name.replace(/_/g, " ")}</div>
                    <div className="text-[10px] text-stone/60">{active ? "已激活" : "未激活"}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Adaptive mission profiles */}
      {!loading && adaptiveStatus?.missions?.length > 0 && (
        <div className="space-y-4">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-stone/60">自适应任务调度</h3>
          {adaptiveStatus.missions.map((m: any) => (
            <div key={m.mission_id} className="rounded-xl border border-taupe bg-ivory p-4">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-graphite">{m.mission_id?.slice(0, 12)}…</span>
                    <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium",
                      m.adaptive_mode === "S3" ? "bg-warm-red/10 text-warm-red" :
                      m.adaptive_mode === "S2" ? "bg-amber/10 text-amber" :
                      "bg-champagne/10 text-champagne"
                    )}>{m.adaptive_mode}</span>
                  </div>
                  <div className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 text-xs">
                    <span className="text-stone/60">Provider:</span>
                    <span className="text-graphite font-mono">{m.selected_provider ?? "—"} / {m.selected_model ?? "—"}</span>
                    <span className="text-stone/60">Agents:</span>
                    <span className="text-graphite">{m.active_agents?.length ?? 0} 个活跃</span>
                    <span className="text-stone/60">Token:</span>
                    <span className="text-graphite">{(m.token_used ?? 0)} / {(m.token_budget ?? 0)}</span>
                    <span className="text-stone/60">工具调用:</span>
                    <span className="text-graphite">{m.tool_calls ?? 0} 次</span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
