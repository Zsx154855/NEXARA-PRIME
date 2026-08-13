"use client";

// ─── 收据链：GET /api/receipts?mission_id=… 按使命懒加载 ───
// 首页不拉全量；选定使命后才整链校验。
// ReceiptChainItem 真实字段 mono 排版：invocation_id / tool_name / status /
// failure_code / reason_code / has_receipt / receipt_verifiable。

import { useCallback, useState } from "react";
import type { ReceiptChainResponse, RuntimeOverview } from "@/types";
import type { NexaraAPI } from "@/lib/api";
import { cn } from "@/lib/utils";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingState";
import { Status } from "@/components/ui/Status";
import { TrustHeader } from "./TrustHeader";
import { Receipt } from "lucide-react";

type ReceiptChainScreenProps = {
  api: NexaraAPI;
  overview: RuntimeOverview | null;
};

/** 完整性总览 + 回执明细。 */
function ReceiptChainView({ data }: { data: ReceiptChainResponse }) {
  const broken =
    !data.chain_intact ||
    data.chain_gaps > 0 ||
    data.unverifiable_receipts > 0 ||
    data.fail_closed_violations > 0;

  const count = (value: number): string =>
    cn("tabular-nums", value > 0 ? "text-danger" : "text-text-primary");

  return (
    <div className="space-y-4">
      {/* 完整性总览 */}
      <section
        aria-label="链完整性总览"
        className="rounded-md border border-border-default bg-surface-elevated px-5 py-4"
      >
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
          <Status
            tone={data.chain_intact ? "success" : "danger"}
            label={data.chain_intact ? "链完整" : "链断裂"}
          />
          <dl className="flex flex-wrap gap-x-6 gap-y-1.5 font-data text-xs text-text-secondary">
            <div className="flex items-baseline gap-1.5">
              <dt className="text-text-tertiary">调用</dt>
              <dd className="tabular-nums text-text-primary">
                {data.total_invocations}
              </dd>
            </div>
            <div className="flex items-baseline gap-1.5">
              <dt className="text-text-tertiary">链缺口</dt>
              <dd className={count(data.chain_gaps)}>{data.chain_gaps}</dd>
            </div>
            <div className="flex items-baseline gap-1.5">
              <dt className="text-text-tertiary">不可验证</dt>
              <dd className={count(data.unverifiable_receipts)}>
                {data.unverifiable_receipts}
              </dd>
            </div>
            <div className="flex items-baseline gap-1.5">
              <dt className="text-text-tertiary">失败关闭违规</dt>
              <dd className={count(data.fail_closed_violations)}>
                {data.fail_closed_violations}
              </dd>
            </div>
          </dl>
        </div>
        {broken && (
          <div className="mt-4">
            <ErrorState
              isInline
              title="收据链存在缺口或违规"
              details={`${data.chain_gaps} 处缺口 · ${data.unverifiable_receipts} 条回执不可验证 · ${data.fail_closed_violations} 起失败关闭违规。该使命的执行完整性无法确认。`}
            />
          </div>
        )}
      </section>

      {/* 回执明细 */}
      <ol className="space-y-2">
        {data.chain.map((item) => (
          <li
            key={item.invocation_id}
            className="rounded-md border border-border-subtle bg-surface-elevated px-4 py-3"
          >
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
              <span className="text-sm font-medium text-text-primary">
                {item.tool_name}
              </span>
              <code className="min-w-0 truncate font-data text-xs text-text-tertiary">
                {item.invocation_id}
              </code>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1.5 font-data text-xs">
              <span className="text-text-secondary">status:{item.status}</span>
              {item.failure_code && (
                <span className="text-danger">failure:{item.failure_code}</span>
              )}
              {item.reason_code && (
                <span className="text-warning">reason:{item.reason_code}</span>
              )}
              <span className="text-text-tertiary">
                receipt:{item.receipt_evidence_id ?? "—"}
              </span>
              <Status
                tone={item.has_receipt ? "success" : "danger"}
                label={item.has_receipt ? "有回执" : "缺回执"}
              />
              {item.has_receipt && (
                <Status
                  tone={item.receipt_verifiable ? "success" : "warning"}
                  label={item.receipt_verifiable ? "可验证" : "不可验证"}
                />
              )}
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

export function ReceiptChainScreen({ api, overview }: ReceiptChainScreenProps) {
  const [missionId, setMissionId] = useState<string>("");
  const [data, setData] = useState<ReceiptChainResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (id: string) => {
      setLoading(true);
      setError(null);
      try {
        const res = await api.getReceipts(id);
        if (res && typeof res === "object" && "chain" in res) {
          setData(res);
        } else {
          setError("该使命没有可校验的收据链");
          setData(null);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
        setData(null);
      } finally {
        setLoading(false);
      }
    },
    [api],
  );

  const handleSelect = (id: string) => {
    setMissionId(id);
    if (!id) {
      setData(null);
      setError(null);
      return;
    }
    void load(id);
  };

  const missions = overview?.missions ?? [];
  const missionLabel =
    missions.find((m) => m.mission_id === missionId)?.title ?? missionId;

  return (
    <div className="space-y-6">
      <TrustHeader
        overline="治理"
        title="收据链"
        subtitle="一次工具调用一条回执。选一个使命，NEXARA 重放整链并做完整性校验——缺口与违规如实呈现。"
      />

      {/* 按使命选择（懒加载） */}
      <div className="flex flex-wrap items-center gap-3">
        <label htmlFor="receipts-mission" className="text-xs text-text-secondary">
          选择使命
        </label>
        <select
          id="receipts-mission"
          value={missionId}
          onChange={(e) => handleSelect(e.target.value)}
          className="h-8 max-w-xs rounded-md border border-border-default bg-surface-elevated px-2 text-sm text-text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus-ring)]"
        >
          <option value="">选择使命以校验收据链</option>
          {missions.map((m) => (
            <option key={m.mission_id} value={m.mission_id}>
              {m.title || m.mission_id}
            </option>
          ))}
        </select>
        {data && (
          <span className="text-xs text-text-tertiary tabular-nums">
            {data.total_invocations} 次调用
          </span>
        )}
      </div>

      {!missionId ? (
        <EmptyState
          icon={<Receipt className="size-6" aria-hidden="true" />}
          title="选择使命后开始整链校验"
          description="收据链按使命懒加载：选定后才会拉取该使命的完整回执链，避免一次性全量加载。"
        />
      ) : loading ? (
        <LoadingState label={`正在校验 ${missionLabel} 的收据链…`} />
      ) : error ? (
        <ErrorState
          title="收据链校验失败"
          details={error}
          actionLabel="重试"
          onAction={() => void load(missionId)}
        />
      ) : data ? (
        <ReceiptChainView data={data} />
      ) : null}
    </div>
  );
}
