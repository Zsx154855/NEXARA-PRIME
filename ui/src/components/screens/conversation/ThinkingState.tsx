import { AgentIndicator } from "@/components/ui/AgentIndicator";
import { LoadingState } from "@/components/ui/LoadingState";

/**
 * 思考状态 — 静止优先（禁 spinner / pulse）：
 *  - AgentIndicator：等待用户态琥珀点 +「正在理解你的意图」
 *  - LoadingState：唯一允许的细线推进 +「柏韩思考中…」文案
 *  LoadingState 自带 role="status" aria-live="polite" 播报。
 */
export function ThinkingState() {
  return (
    <div className="flex max-w-sm flex-col gap-2">
      <AgentIndicator actor="柏韩" activity="正在理解你的意图" isWaiting />
      <LoadingState label="柏韩思考中…" />
    </div>
  );
}
