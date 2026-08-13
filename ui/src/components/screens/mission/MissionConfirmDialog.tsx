// 使命控制动作（暂停 / 恢复 / 回滚 / 安全模式）确认弹窗
import { useRef } from "react";
import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/ui/ErrorState";
import { useDialogA11y } from "@/components/ui/dialog-a11y";

interface MissionConfirmDialogProps {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  isDanger?: boolean;
  isBusy?: boolean;
  error?: string | null;
  onConfirm: () => void;
  onCancel: () => void;
}

export function MissionConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  isDanger,
  isBusy,
  error,
  onConfirm,
  onCancel,
}: MissionConfirmDialogProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  useDialogA11y(open, onCancel, panelRef);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-graphite/30 px-4 backdrop-blur-sm">
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="w-full max-w-md animate-fade-in rounded-xl border border-border-default bg-ivory p-6 shadow-xl"
      >
        <h3 className="text-base font-semibold text-text-primary">{title}</h3>
        <p className="mt-2 text-sm leading-relaxed text-text-secondary">
          {description}
        </p>
        {error && (
          <ErrorState
            isInline
            title="操作失败"
            details={error}
            className="mt-4"
          />
        )}
        <div className="mt-5 flex justify-end gap-3">
          <Button variant="quiet" onClick={onCancel} disabled={isBusy}>
            取消
          </Button>
          <Button
            variant={isDanger ? "danger" : "primary"}
            onClick={onConfirm}
            isBusy={isBusy}
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
