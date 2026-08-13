// ─── 知识：/api/knowledge-universe 投影 ───
// 后端模块未就绪（503）时如实呈现「知识库模块未就绪」；
// 成功时按返回字段原貌展示，不做字段虚构。

"use client";

import { useCallback, useEffect, useState } from "react";
import { BookOpen } from "lucide-react";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingState";
import { Status } from "@/components/ui/Status";
import { MemoryHeader } from "./MemoryHeader";
import { MemorySubNav } from "./MemorySubNav";
import { fetchKnowledgeUniverse } from "./knowledge";

export function MemoryKnowledgeScreen() {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<number | undefined>(undefined);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const result = await fetchKnowledgeUniverse();
    if (result.type === "success" && result.data) {
      setData(result.data);
    } else {
      setError(result.error ?? "未知错误");
      setStatus(result.status);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const moduleNotReady = error !== null && status === 503;

  return (
    <div className="space-y-8">
      <MemoryHeader
        title="知识"
        subtitle="文档库的知识宇宙视图，由 /api/knowledge-universe 提供。"
      />
      <MemorySubNav />

      {loading ? (
        <LoadingState label="正在读取知识宇宙…" />
      ) : error ? (
        <ErrorState
          title={moduleNotReady ? "知识库模块未就绪" : "知识宇宙读取失败"}
          details={
            moduleNotReady
              ? "后端返回 503：knowledge_universe 模块未随运行时加载。该模块就绪后，此页会展示文档库扫描结果；若持续如此，请检查运行时侧该模块的安装与配置。"
              : error
          }
          actionLabel="重试"
          onAction={() => void load()}
        />
      ) : !data ? (
        <EmptyState
          icon={<BookOpen className="size-6" aria-hidden="true" />}
          title="知识宇宙为空"
          description="后端就绪但未返回任何内容。可稍后重试，或先确认文档库路径（NEXARA_VAULT_PATH）是否已配置。"
          actionLabel="重新加载"
          onAction={() => void load()}
        />
      ) : (
        <div className="max-w-2xl">
          <Status tone="success" label="知识库模块已就绪" />

          <dl className="mt-6 divide-y divide-border-subtle">
            {Object.entries(data).map(([key, value]) => {
              if (Array.isArray(value)) {
                return (
                  <div
                    key={key}
                    className="flex items-baseline justify-between gap-6 py-3"
                  >
                    <dt className="font-data text-sm text-text-secondary">{key}</dt>
                    <dd className="font-data text-sm text-text-primary">
                      {value.length} 项
                    </dd>
                  </div>
                );
              }
              if (typeof value === "number" || typeof value === "string") {
                return (
                  <div
                    key={key}
                    className="flex items-baseline justify-between gap-6 py-3"
                  >
                    <dt className="font-data text-sm text-text-secondary">{key}</dt>
                    <dd className="font-data text-sm text-text-primary">
                      {String(value)}
                    </dd>
                  </div>
                );
              }
              return null;
            })}
          </dl>

          <p className="mt-6 text-xs text-text-tertiary">
            字段以 /api/knowledge-universe 返回原貌呈现。
          </p>
        </div>
      )}
    </div>
  );
}
