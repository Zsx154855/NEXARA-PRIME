"use client";

import { useEffect } from "react";

/**
 * 对话框焦点管理：Escape 关闭、打开时聚焦首个可聚焦元素、
 * 关闭时焦点归还触发元素。
 */
export function useDialogA11y(
  isOpen: boolean,
  onClose: () => void,
  panelRef: React.RefObject<HTMLElement | null>,
): void {
  useEffect(() => {
    if (!isOpen) return;

    const previouslyFocused = document.activeElement as HTMLElement | null;

    const focusableSelector =
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
    const panel = panelRef.current;
    const firstFocusable = panel?.querySelector<HTMLElement>(focusableSelector);
    firstFocusable?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
    };
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      previouslyFocused?.focus();
    };
  }, [isOpen, onClose, panelRef]);
}
