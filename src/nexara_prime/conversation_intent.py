"""Runtime-owned intent classification for Conversation execution modes.

The UI declares a policy mode; it does not decide whether a turn is an action.
This classifier is deliberately small and explainable: it combines action,
target, outcome, and sentence-shape signals and returns evidence for the
durable conversation metadata. It never selects a Provider or bypasses policy.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class IntentDecision:
    intent: str
    confidence: float
    reasons: tuple[str, ...]


class RuntimeIntentClassifier:
    """Classify a user turn as ordinary chat or an actionable mission."""

    _ACTION_TERMS = (
        "检查", "查看", "读取", "分析", "总结", "整理", "生成", "创建",
        "执行", "运行", "修复", "解决", "处理", "汇报", "inspect", "check",
        "analyze", "summarize", "generate", "create", "execute", "run", "fix",
        "resolve", "report",
    )
    _TARGET_TERMS = (
        "状态", "问题", "任务", "系统", "运行", "文件", "报告", "对话", "mission",
        "runtime", "workspace", "status", "issue", "task", "report", "file",
    )
    _OUTCOME_TERMS = (
        "并", "然后", "之后", "为我", "向我", "自动", "直到", "并且", "and", "then",
        "for me", "automatically",
    )
    _QUESTION_TERMS = ("谁", "什么", "为何", "为什么", "怎么", "记得", "who", "what", "why", "how")

    @classmethod
    def classify(cls, content: str) -> IntentDecision:
        text = re.sub(r"\s+", " ", content.strip()).lower()
        if not text:
            return IntentDecision("chat", 1.0, ("empty_turn",))

        actions = tuple(term for term in cls._ACTION_TERMS if term in text)
        targets = tuple(term for term in cls._TARGET_TERMS if term in text)
        outcomes = tuple(term for term in cls._OUTCOME_TERMS if term in text)
        is_question = text.endswith(("?", "？")) or any(term in text for term in cls._QUESTION_TERMS)
        clauses = len(re.findall(r"[,，;；。.!！?？]", text))

        # An action requires at least two independent signals. A plain
        # question remains chat even if it mentions a runtime or task.
        actionable = bool(actions and targets and (outcomes or clauses >= 2))
        if is_question and not outcomes and len(actions) < 2:
            actionable = False

        if actionable:
            confidence = min(0.98, 0.68 + 0.08 * min(len(actions), 2) + 0.06 * min(len(targets), 2) + (0.06 if outcomes else 0.0))
            reasons = (
                f"action_signals={','.join(actions[:4])}",
                f"target_signals={','.join(targets[:4])}",
                f"outcome_signals={','.join(outcomes[:4]) or 'none'}",
                f"clause_count={clauses}",
            )
            return IntentDecision("mission", round(confidence, 2), reasons)

        reasons = (
            f"action_signals={','.join(actions[:4]) or 'none'}",
            f"target_signals={','.join(targets[:4]) or 'none'}",
            f"question_shape={'yes' if is_question else 'no'}",
            f"clause_count={clauses}",
        )
        return IntentDecision("chat", 0.9 if is_question else 0.82, reasons)
