// 创建成功：任务已进入审批队列（人类审批门，永不自动绕过）。

import { CheckCircle2, FileText, Info } from "lucide-react";
import { Button } from "@/components/ui/Button";

interface SuccessViewProps {
  missionId: string | null;
  onDone: () => void;
}

export function SuccessView({ missionId, onDone }: SuccessViewProps) {
  return (
    <div className="flex flex-col items-center gap-5 py-12">
      <div className="flex h-16 w-16 items-center justify-center rounded-full bg-success/10">
        <CheckCircle2 className="h-8 w-8 text-success" />
      </div>
      <div className="text-center">
        <h2 className="text-base font-semibold text-text-primary">任务创建成功</h2>
        <p className="mt-2 text-xs text-text-secondary">
          任务 ID：
          <code className="ml-1 rounded bg-surface-subtle px-1.5 py-0.5 font-data text-xs text-text-primary">
            {missionId}
          </code>
        </p>
      </div>
      <div className="flex items-start gap-2 rounded-lg border border-border-default bg-surface-subtle p-3 text-xs leading-relaxed text-text-secondary">
        <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-info" />
        任务已进入审批队列。请在审批中心查看并处理。
      </div>
      <div className="mt-2 flex flex-wrap justify-center gap-3">
        <Button variant="ghost" onClick={onDone}>
          返回
        </Button>
        <Button onClick={onDone}>
          <FileText className="h-4 w-4" />
          查看审批队列
        </Button>
      </div>
    </div>
  );
}
