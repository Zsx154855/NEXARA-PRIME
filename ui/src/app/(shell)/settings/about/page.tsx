import type { Metadata } from "next";
import { BrandMark } from "@/components/brand/BrandMark";

export const metadata: Metadata = {
  title: "关于 · 柏韩 NEXARA",
};

/**
 * 设置 — 关于（品牌与宪章声明，静态文案无运行时事实）
 */
export default function SettingsAboutPage() {
  return (
    <div className="mx-auto flex max-w-xl flex-col gap-4 px-2 py-6">
      <div className="flex items-center gap-3">
        <BrandMark className="size-10 rounded-[9px]" />
        <div>
          <h1 className="font-editorial text-xl text-text-primary">柏韩 · NEXARA</h1>
          <p className="text-xs text-text-secondary">本地单用户模式</p>
        </div>
      </div>
      <p className="text-sm leading-relaxed text-text-secondary">
        把你想做的事说给 NEXARA。它把它变成一份你看得懂的计划、一道道你说了算的门、
        一条条能查证的结果，以及它记住的东西。复杂更稳，简单更快，高风险永远你拍板，
        结果永远可验证。
      </p>
      <dl className="mt-2 space-y-2 border-t border-border-subtle pt-4 text-xs text-text-secondary">
        <div className="flex justify-between gap-4">
          <dt>治理宪章</dt>
          <dd className="font-data">NSEC V2.1 · 19 章 55 条</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt>人类控制</dt>
          <dd>批准 · 暂停 · 接管 · 回滚</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt>认证状态</dt>
          <dd className="text-warning">AUTH BACKEND REQUIRED</dd>
        </div>
      </dl>
    </div>
  );
}
