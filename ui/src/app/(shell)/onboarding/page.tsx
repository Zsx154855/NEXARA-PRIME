"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { Status } from "@/components/ui/Status";
import { useRuntimeData } from "@/lib/runtime-context";

/**
 * ONBOARDING — 七步引导。
 * 诚实落地：每步标注真实数据来源；依赖缺失写入端点/认证的步骤
 * 标 PLANNED（不伪造成功）。
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

type StepProps = {
  index: number;
  title: string;
  planned?: boolean;
  children: React.ReactNode;
};

function Step({ index, title, planned, children }: StepProps) {
  return (
    <section aria-labelledby={`ob-step-${index}`} className="flex gap-4">
      <div className="flex flex-col items-center">
        <span className="flex size-7 items-center justify-center rounded-full bg-graphite text-xs font-semibold text-ivory">
          {index}
        </span>
        {index < 7 && <span className="mt-1 w-px flex-1 bg-border-subtle" aria-hidden="true" />}
      </div>
      <div className="flex-1 pb-8">
        <h2 id={`ob-step-${index}`} className="mb-1 flex items-center gap-2 text-sm font-semibold text-text-primary">
          {title}
          {planned && <Badge tone="warning">PLANNED</Badge>}
        </h2>
        <div className="text-sm leading-relaxed text-text-secondary">{children}</div>
      </div>
    </section>
  );
}

export default function OnboardingPage() {
  const { overview } = useRuntimeData();
  const adapters = overview?.system.adapters ?? {};
  const adapterEntries = Object.entries(adapters);

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 px-2 py-6">
      <header>
        <h1 className="font-editorial text-2xl text-text-primary">认识 NEXARA</h1>
        <p className="mt-1 text-sm text-text-secondary">
          七步之后，你会知道它如何工作、边界在哪、以及第一件值得托付的事是什么。
        </p>
      </header>

      <Step index={1} title="认识 NEXARA">
        柏韩是一个受治理的 Agent 工作闭环：你把意图说给它，它变成一份有契约、
        有批准、有证据、有记忆的工作。复杂更稳，简单更快，高风险永远你拍板，
        结果永远可验证。当前系统模式：
        <Status tone={overview?.system.healthy ? "success" : "warning"} label={overview?.system.healthy ? "运行正常" : "运行时异常"} className="ml-2" />
      </Step>

      <Step index={2} title="告诉 NEXARA 你是谁" planned>
        姓名、关注领域与风险偏好。当前为本地单用户模式，偏好写入能力为
        PLANNED（后端无对应端点）；接线前 NEXARA 以默认边界工作。
      </Step>

      <Step index={3} title="设置工作方式" planned>
        选择默认执行档：快问快答（S0）／帮我做（S1）／带我看（S2）／一切受审（S3）。
        当前可在对话中按次选择执行模式（对话/自动/使命）；默认档持久化为 PLANNED。
      </Step>

      <Step index={4} title="权限与安全边界">
        本地单用户模式下权限面全开，安全边界由治理引擎与审批门保障：
        高风险动作（R2/R3）必须经你批准；NSEC V2.1 约束人类始终可暂停、接管、回滚。
        用户级权限配置为 PLANNED（AUTH BACKEND REQUIRED）。
      </Step>

      <Step index={5} title="连接工具与能力">
        当前连接器状态（只读投影，连接配置标 CONNECTOR_REQUIRED）：
        {adapterEntries.length === 0 ? (
          <span className="ml-2 text-xs text-text-tertiary">运行时未报告连接器状态。</span>
        ) : (
          <span className="ml-2 inline-flex flex-wrap gap-1.5 align-middle">
            {adapterEntries.map(([key, connected]) => (
              <Badge key={key} tone={connected ? "success" : "neutral"}>
                {ADAPTER_LABELS[key] ?? key}：{connected ? "已连接" : "未连接"}
              </Badge>
            ))}
          </span>
        )}
      </Step>

      <Step index={6} title="第一次任务">
        现在就可以开始：在
        <Link href="/conversation" className="mx-1 text-gold-text underline underline-offset-2">
          对话
        </Link>
        里说出你要做的事（建议从读取/总结类低风险任务开始），NEXARA 会确认理解、
        编译成使命、需要时请求批准，然后执行并留下证据。
      </Step>

      <Step index={7} title="第一次结果">
        任务完成后，到
        <Link href="/trust/evidence" className="mx-1 text-gold-text underline underline-offset-2">
          治理 → 证据
        </Link>
        查看它凭什么说完成：谁、何时、做了什么、如何验证（sha256 证据链）。
        值得记的经验会按置信度自动沉淀到
        <Link href="/memory" className="mx-1 text-gold-text underline underline-offset-2">
          记忆
        </Link>
        ——那是 NEXARA 下次更懂你的起点。
      </Step>

      <footer className="border-t border-border-subtle pt-4">
        <p className="text-xs text-text-secondary">
          你的 NEXARA 已准备好。开始第一次对话吧。
        </p>
      </footer>
    </div>
  );
}
