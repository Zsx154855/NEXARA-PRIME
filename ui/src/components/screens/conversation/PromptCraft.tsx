"use client";

import { useMemo, useState } from "react";
import { Copy, Check, Sparkles, Wand2, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import {
  toProfessionalPrompt,
  toPromptText,
} from "@/lib/promptify";

type PromptCraftProps = {
  /** 预填的自然语言（通常来自当前草稿或选中文本） */
  initialText: string;
  onUsePrompt: (promptText: string) => void;
};

/**
 * 白话转专业提示词 — 确定性转换，无模型调用。
 * 将自然语言整理为 角色/背景/目标/约束/输出 的结构化 Prompt，
 * 支持复制或一键回填到输入框发送。
 */
export function PromptCraft({ initialText, onUsePrompt }: PromptCraftProps) {
  const [open, setOpen] = useState(false);
  const [source, setSource] = useState(initialText);
  const [copied, setCopied] = useState(false);

  const prompt = useMemo(
    () => (source.trim() ? toProfessionalPrompt(source) : null),
    [source],
  );
  const promptText = useMemo(
    () => (prompt ? toPromptText(prompt) : ""),
    [prompt],
  );

  if (!open) {
    return (
      <div className="flex items-center justify-between border-t border-border-subtle px-5 py-2">
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="inline-flex items-center gap-1.5 text-xs text-text-tertiary transition-colors hover:text-text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus-ring)]"
          aria-label="打开白话转专业提示词"
        >
          <Wand2 className="size-3.5" aria-hidden="true" />
          白话转专业提示词
        </button>
      </div>
    );
  }

  return (
    <div className="border-t border-border-subtle bg-surface-subtle/60 px-5 py-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="inline-flex items-center gap-1.5 text-xs font-medium text-text-secondary">
          <Sparkles className="size-3.5" aria-hidden="true" />
          白话转专业提示词
        </span>
        <Button
          variant="quiet"
          size="sm"
          onClick={() => setOpen(false)}
          aria-label="关闭"
        >
          <X className="size-3.5" aria-hidden="true" />
        </Button>
      </div>

      <div className="space-y-2">
        <textarea
          value={source}
          onChange={(e) => setSource(e.target.value)}
          rows={2}
          placeholder="用大白话说出你的需求，例如：帮我写一个检查磁盘剩余空间的脚本，不要删除任何文件"
          className="w-full resize-none rounded-md border border-border-default bg-surface-base px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-border-focus focus:outline-none"
          aria-label="白话需求输入"
        />

        {prompt && (
          <div className="rounded-md border border-border-subtle bg-surface-elevated p-3">
            <pre className="max-h-48 overflow-y-auto whitespace-pre-wrap font-data text-xs leading-relaxed text-text-secondary">
              {promptText}
            </pre>
            <div className="mt-2 flex items-center justify-end gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  void navigator.clipboard?.writeText(promptText);
                  setCopied(true);
                  setTimeout(() => setCopied(false), 1600);
                }}
              >
                {copied ? (
                  <Check className="size-3.5" aria-hidden="true" />
                ) : (
                  <Copy className="size-3.5" aria-hidden="true" />
                )}
                {copied ? "已复制" : "复制"}
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={() => {
                  onUsePrompt(promptText);
                  setOpen(false);
                }}
              >
                <Wand2 className="size-3.5" aria-hidden="true" />
                使用此提示词
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
