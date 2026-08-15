// 使命列表：搜索 + 状态筛选 + 空态（EmptyState）。状态用 Status（三重编码），风险用 Badge（语义色）。

import { useState } from "react";
import { ChevronRight, Filter, Rocket, Search } from "lucide-react";
import type { MissionSnapshot } from "@/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { Status } from "@/components/ui/Status";
import { formatDate } from "@/lib/utils";
import { filterProductMissions } from "@/lib/presentation";
import { riskLabel, riskTone, stateLabel, stateTone } from "./constants";

const STATUS_OPTIONS = [
  "Intent",
  "Approval",
  "Execution",
  "Completed",
  "Failed",
  "Blocked",
] as const;

const INPUT_CLASS =
  "rounded-md border border-border-default bg-surface-base text-sm text-text-primary placeholder:text-text-tertiary focus:border-border-focus focus:outline-none focus:ring-1 focus:ring-border-focus/30";

interface MissionListProps {
  missions: MissionSnapshot[];
  onSelect: (missionId: string) => void;
  onCreate: () => void;
}

export function MissionList({ missions, onSelect, onCreate }: MissionListProps) {
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  // P1-DATA-BOUNDARY-001：默认产品视图排除 QA/测试使命（数据不删除，仅视图过滤）
  const productMissions = filterProductMissions(missions);

  const filtered = productMissions.filter((m) => {
    const matchesSearch =
      !searchTerm ||
      (m.title ?? m.objective ?? m.mission_id)
        .toLowerCase()
        .includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === "all" || m.state === statusFilter;
    return matchesSearch && matchesStatus;
  });
  const sorted = [...filtered].reverse();

  return (
    <div className="animate-fade-in space-y-6">
      {/* 页头 */}
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-text-primary">任务</h1>
          <p className="mt-0.5 text-sm text-text-secondary">
            {missions.length > 0 ? `${missions.length} 个任务` : "创建你的第一个任务"}
          </p>
        </div>
        <Button variant="gold" onClick={onCreate}>
          <Rocket className="h-4 w-4" />
          创建任务
        </Button>
      </div>

      {/* 搜索 + 筛选 */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-52 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-tertiary" />
          <input
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="搜索任务…"
            aria-label="搜索任务"
            className={INPUT_CLASS + " w-full py-2 pl-10 pr-4"}
          />
        </div>
        <div className="relative">
          <Filter className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-tertiary" />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            aria-label="按状态筛选"
            className={INPUT_CLASS + " appearance-none py-2 pl-10 pr-8"}
          >
            <option value="all">全部状态</option>
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {stateLabel(s)}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* 列表 / 空态 */}
      {sorted.length === 0 ? (
        missions.length === 0 ? (
          <EmptyState
            title="还没有任务"
            description="定义第一个任务目标，NEXARA 会生成执行规划，并在任何执行前等待你的审批。"
            actionLabel="创建任务"
            onAction={onCreate}
            icon={<Rocket className="h-5 w-5" />}
          />
        ) : (
          <EmptyState
            title="没有匹配的任务"
            description="调整搜索关键词或状态筛选后再试一次。"
          />
        )
      ) : (
        <ul className="space-y-2">
          {sorted.map((m) => (
            <li key={m.mission_id}>
              <button
                type="button"
                onClick={() => onSelect(m.mission_id)}
                className="flex w-full items-center gap-4 rounded-lg border border-border-default bg-surface-elevated p-4 text-left transition-colors hover:border-accent-soft hover:shadow-[0_1px_3px_rgba(0,0,0,0.06)]"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
                    <span className="min-w-0 truncate text-sm font-medium text-text-primary">
                      {m.title ?? m.objective ?? m.mission_id}
                    </span>
                    <Status tone={stateTone(m.state)} label={stateLabel(m.state)} />
                    <Badge tone={riskTone(m.risk_level)}>{riskLabel(m.risk_level)}</Badge>
                  </div>
                  <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-text-secondary">
                    <code className="font-data">{m.mission_id.slice(0, 14)}…</code>
                    {m.created_at && <span>{formatDate(m.created_at)}</span>}
                  </div>
                </div>
                <ChevronRight className="h-4 w-4 shrink-0 text-text-tertiary" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
