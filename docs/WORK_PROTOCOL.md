# Working protocol (applies to every phase, not once at the start)

## 1. Skill activation is a step, not a memory
At the start of every phase and before every review:
1. `rg -l '<phase keywords>' /var/minis/skills/*/SKILL.md` to find candidates.
2. Read the SKILL.md of the 2–4 that match (not the whole catalogue).
3. Record name → purpose → used-for in `PROJECT_SKILLS_LEDGER.md`.
4. If a token-heavy phase (reading many files, large diffs, long logs), load
   `context-discipline` and follow it: outline first, ranges, cap output, offload
   bulk reading to a sub-agent.

## 2. When to stop
Stop only for:
- a decision that needs the owner (money, production, public release, irreversible),
- a hard environment blocker (with the exact error and the minimal unblock),
- delivery of a phase with evidence.
Never stop because "the next step is large" or "I should report". Report at
checkpoints, then continue.

## 3. Definition of done per change
`QUALITY_STANDARD.md` — compile, lint, tests, route truth, gate check, drift,
secret scan, review, changelog/ADR, rollback line.

## 4. Evidence format
Every claim carries `command → exit code → one-line result`. No command, mark
`UNVERIFIED`.

## 5. Review is independent
Author never signs their own security/architecture change. Dispatch a fresh
sub-agent with the diff and the standard; fix what it finds before claiming done.

## 6. CI operations (self-hosted)
- The quality workflow runs on the registered macOS runner (hosted runners are
  blocked by an account billing issue). It executes the same
  `scripts/quality/gate.sh` a developer runs, plus a UI build and an
  `npm audit --audit-level=high`.
- The runner is a user LaunchAgent (`~/Library/LaunchAgents/actions.runner.*`)
  with its own `caffeinate -dimsu` agent (`local.nexara.caffeinate`) so the
  machine does not sleep mid-job.
- If a job is cancelled or the machine sleep-walks, the runner can report
  `A session for this runner already exists`; cancel the stale run in the UI and
  the listener reconnects within seconds. Restarting the service does not clear
  a server-side session.
