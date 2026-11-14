# agent-autoloop wiring for NEXARA continuation (proposal only)

Date: 2026-11-15. Status: NOT ENABLED. No active rule, config, service, or DB was modified.

## Current state (verified)

- The loop is already installed and running (`launchd` pid 763; config at
  `~/.agent-autoloop/config.json`, hub `127.0.0.1:3350`), with 6 active rules
  (try, morning brief, nightly check, vault check, case digest, backup).
- `agents.dsh` runs `~/.local/bin/dsh-next-agent` (a separate dsh install that
  injects `DEEPSEEK_API_KEY`) with a 300 s timeout. Any event routed to it can
  spend paid model quota.
- There is no NEXARA rule; nothing currently dispatches `recovery_entry.py`.

## Minimal wiring (two options, choose one)

### Option A — event-triggered, model-backed (recommended when cost approved)

Append to `rules` (validated in a temp copy; `agent-autoloop check` returns
`规则没问题`):

```json
{
  "name": "NEXARA 接力",
  "when": {"source": "local", "types": ["nexara.*"]},
  "to": "dsh",
  "cwd": "/Users/agentos/Worktrees/NEXARA-TASK3-RECEIPT-20261114",
  "prompt": "只做一件事：运行 /Users/agentos/NEXARA-PRIME/.venv/bin/python scripts/continuation/recovery_entry.py /Users/agentos/NEXARA_GATE_RESULTS/TASK3_RECEIPT_20261114/next_task.json --advance --max-tasks 1 --json。只报告 JSON 结果和下一步；遇到 already_running / awaiting_verification / next_task_not_advanced / 任一阻塞时停止，不重试、不改 checkpoint、不合并 main、不部署、不安装服务。",
  "tell": "needed"
}
```

Emit the event only after a checkpoint update:
`agent-autoloop emit nexara.checkpoint --subject <task-id> --summary "checkpoint advanced"`.
This spends model quota and must be approved by the user first.

### Option B — no model, notification only

Route `nexara.*` to a `command` agent that appends the event to a local log;
a human then runs `recovery_entry.py`. Zero model cost but no unattended
continuation.

## Preconditions and limits

- Only one rule/agent may dispatch a given checkpoint; `recovery_entry.py`'s
  lock is the final guard (`already_running`, live-owner protection).
- `--advance --max-tasks 1` bounds one invocation; no daemon is installed.
- Do not point `cwd` at the main checkout; the state directory is
  `<checkpoint_dir>/.continuation` (canonical absolute).
- Real dsh success is only `awaiting_verification`; the checkpoint must record
  `status=completed`, non-empty evidence, and QA pass before `--verify` moves
  the lock to `done`.

## Rollback

1. `agent-autoloop pause "NEXARA 接力"` (stops dispatch immediately).
2. Remove the rule from `~/.agent-autoloop/rules.json` (or restore
   `rules.json.bak-20261109-081544`).
3. `agent-autoloop check` → expect `规则没问题`.
4. No service, DB, or plugin was installed, so no further rollback is needed.
5. Existing in-flight work is untouched; locks live under the checkpoint's
   `.continuation/` and can be inspected with `recovery_entry.py --status`.
