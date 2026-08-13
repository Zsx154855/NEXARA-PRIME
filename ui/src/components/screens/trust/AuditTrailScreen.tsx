"use client";

// ─── 审计日志：GET /api/events/:mission_id 按对象重放 ───
// 选定使命后重放事件流（event_type / actor / timestamp），按时间升序叙事；
// 负载以 <details> 折叠，不铺满页面。事件为中性数据，无状态语义色。

import { useCallback, useEffect, useMemo, useState } from "react";
import type { Event, RuntimeOverview } from "@/types";
import type { NexaraAPI } from "@/lib/api";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingState";
import { TrustHeader } from "./TrustHeader";
import { ScrollText } from "lucide-react";

type AuditTrailScreenProps = {
  api: NexaraAPI;
  overview: RuntimeOverview | null;
};

function formatEventTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

/** 事件时间线：发丝线 + 金点（装饰），负载折叠。 */
function EventTimeline({ events }: { events: Event[] }) {
  return (
    <ol className="relative ml-1 space-y-0 border-l border-border-subtle pl-5">
      {events.map((ev) => {
        const hasPayload =
          ev.payload !== null &&
          typeof ev.payload === "object" &&
          Object.keys(ev.payload).length > 0;
        return (
          <li key={ev.event_id} className="relative pb-6 last:pb-0">
            <span
              className="absolute -left-6 top-1.5 size-2 rounded-full bg-gold-text"
              aria-hidden="true"
            />
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <code className="font-data text-xs font-medium text-text-primary">
                {ev.event_type}
              </code>
              <span className="text-xs text-text-secondary">
                actor:{ev.actor}
              </span>
              <time className="text-xs text-text-tertiary" dateTime={ev.timestamp}>
                {formatEventTime(ev.timestamp)}
              </time>
            </div>
            <div className="mt-1 flex flex-wrap gap-x-4 font-data text-xs text-text-tertiary">
              <span>
                {ev.aggregate_type}:{ev.aggregate_id}
              </span>
              <span>trace:{ev.trace_id}</span>
            </div>
            {hasPayload && (
              <details className="mt-2">
                <summary className="cursor-pointer text-xs text-gold-text transition-colors hover:text-gold-text/80 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus-ring)]">
                  查看负载
                </summary>
                <pre className="mt-2 max-h-48 overflow-auto rounded-md border border-border-subtle bg-surface-subtle p-3 font-data text-xs leading-relaxed text-text-secondary">
                  {JSON.stringify(ev.payload, null, 2)}
                </pre>
              </details>
            )}
          </li>
        );
      })}
    </ol>
  );
}

export function AuditTrailScreen({ api, overview }: AuditTrailScreenProps) {
  const [objectId, setObjectId] = useState<string>("");
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (id: string) => {
      setLoading(true);
      setError(null);
      try {
        const data = await api.getEvents(id);
        setEvents(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
        setEvents([]);
      } finally {
        setLoading(false);
      }
    },
    [api],
  );

  useEffect(() => {
    if (!objectId) return;
    void load(objectId);
  }, [load, objectId]);

  const handleSelect = (id: string) => {
    setObjectId(id);
    if (!id) {
      setEvents([]);
      setError(null);
    }
  };

  const missions = overview?.missions ?? [];
  const objectLabel =
    missions.find((m) => m.mission_id === objectId)?.title ?? objectId;

  /** 重放 = 按时间升序的事件流。 */
  const replay = useMemo(
    () =>
      [...events].sort(
        (a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp),
      ),
    [events],
  );

  return (
    <div className="space-y-6">
      <TrustHeader
        overline="治理"
        title="审计日志"
        subtitle="NEXARA 的事件流按对象重放：谁、以什么身份、在什么时间、留下了什么。"
      />

      {/* 按对象选择 */}
      <div className="flex flex-wrap items-center gap-3">
        <label htmlFor="audit-object" className="text-xs text-text-secondary">
          选择对象
        </label>
        <select
          id="audit-object"
          value={objectId}
          onChange={(e) => handleSelect(e.target.value)}
          className="h-8 max-w-xs rounded-md border border-border-default bg-surface-elevated px-2 text-sm text-text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus-ring)]"
        >
          <option value="">选择使命以重放事件流</option>
          {missions.map((m) => (
            <option key={m.mission_id} value={m.mission_id}>
              {m.title || m.mission_id}
            </option>
          ))}
        </select>
        {events.length > 0 && (
          <span className="text-xs text-text-tertiary tabular-nums">
            {events.length} 个事件
          </span>
        )}
      </div>

      {!objectId ? (
        <EmptyState
          icon={<ScrollText className="size-6" aria-hidden="true" />}
          title="选择对象后重放事件流"
          description="审计按对象懒加载：选定使命后，从最早的事件开始按时间顺序重放。"
        />
      ) : loading ? (
        <LoadingState label={`正在重放 ${objectLabel} 的事件流…`} />
      ) : error ? (
        <ErrorState
          title="事件流重放失败"
          details={error}
          actionLabel="重试"
          onAction={() => void load(objectId)}
        />
      ) : replay.length === 0 ? (
        <EmptyState
          title="该对象暂无事件"
          description="还没有记录到任何事件——使命开始执行后，这里会出现完整的时间线。"
        />
      ) : (
        <EventTimeline events={replay} />
      )}
    </div>
  );
}
