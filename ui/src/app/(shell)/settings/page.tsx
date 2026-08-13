"use client";

import { useEffect, useState } from "react";
import { Status } from "@/components/ui/Status";
import { Badge } from "@/components/ui/Badge";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingState";
import { useRuntimeData } from "@/lib/runtime-context";
import type { HealthResponse } from "@/types";

/**
 * 设置 — 只读镜像。
 * 配置为环境变量驱动（NEXARA_MODEL_PROVIDER / NEXARA_DB_PATH 等），
 * 运行时无可写项；变更方式 = 修改 env 后重启。
 */
type SettingsRowProps = {
  label: string;
  value: string;
  mono?: boolean;
  tone?: "success" | "warning" | "neutral";
};

function SettingsRow({ label, value, mono, tone = "neutral" }: SettingsRowProps) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-border-subtle py-3">
      <dt className="text-sm text-text-secondary">{label}</dt>
      <dd
        className={
          mono ? "font-data text-sm text-text-primary" : "text-sm text-text-primary"
        }
      >
        {tone === "success" && <Status tone="success" label={value} className="mr-2" />}
        {tone === "warning" && <Status tone="warning" label={value} className="mr-2" />}
        {tone === "neutral" && value}
      </dd>
    </div>
  );
}

export default function SettingsPage() {
  const { overview, stats, loading, error, refresh, api } = useRuntimeData();
  const [health, setHealth] = useState<HealthResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getHealth()
      .then((h) => {
        if (!cancelled) setHealth(h);
      })
      .catch(() => {
        // 健康端点失败不阻塞页面——如实显示未提供
      });
    return () => {
      cancelled = true;
    };
  }, [api]);

  if (loading && overview === null) {
    return <LoadingState label="正在读取运行时配置…" />;
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 px-2 py-4">
      {error && (
        <ErrorState
          title="运行时未连接"
          details="无法读取运行时配置。检查服务是否运行于 127.0.0.1:8765，然后重试。"
          actionLabel="重试"
          onAction={refresh}
        />
      )}

      <section aria-labelledby="settings-runtime">
        <h2 id="settings-runtime" className="mb-1 text-sm font-semibold text-text-primary">
          运行时配置
        </h2>
        <p className="mb-3 text-xs text-text-secondary">
          配置由环境变量驱动，运行时只读。变更方式：修改 env 后重启服务。
        </p>
        <dl>
          <SettingsRow
            label="系统模式"
            value={overview?.system.mode ?? "未提供"}
          />
          <SettingsRow
            label="人类控制"
            value="已启用"
            tone={overview?.system.human_control === false ? "warning" : "success"}
          />
          <SettingsRow
            label="Provider"
            value={stats?.provider ?? "未提供"}
            mono
          />
          <SettingsRow
            label="Provider 可用性"
            value={stats === null ? "未提供" : stats.provider_available ? "可用" : "不可用"}
            tone={stats === null ? "neutral" : stats.provider_available ? "success" : "warning"}
          />
          <SettingsRow
            label="运行模式"
            value={stats?.mock_mode ? "mock（模拟 provider）" : "真实 provider"}
            tone={stats?.mock_mode ? "warning" : "neutral"}
          />
          <SettingsRow label="数据库路径" value={health?.db_path ?? "未提供"} mono />
          <SettingsRow
            label="恢复状态"
            value={stats?.recovery_state ?? "未提供"}
          />
        </dl>
      </section>

      <section aria-labelledby="settings-auth">
        <h2 id="settings-auth" className="mb-1 text-sm font-semibold text-text-primary">
          认证与身份
        </h2>
        <p className="mb-3 text-xs leading-relaxed text-text-secondary">
          当前为本地单用户模式：无登录/注册，审批与审计以 actor=&quot;human&quot; 记录。
          用户认证为 PLANNED 能力（身份层未接入 API）。
        </p>
        <Badge tone="warning">AUTH BACKEND REQUIRED</Badge>
      </section>

      <section aria-labelledby="settings-guide">
        <h2 id="settings-guide" className="mb-1 text-sm font-semibold text-text-primary">
          引导
        </h2>
        <p className="text-sm text-text-secondary">
          想重新走一遍七步引导？
          <a href="/onboarding" className="mx-1 text-gold-text underline underline-offset-2">
            认识 NEXARA
          </a>
        </p>
      </section>
    </div>
  );
}
