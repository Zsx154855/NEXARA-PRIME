# 柏韩 · NEXARA PRIME

柏韩 (Bǎi Hán) is a Human-Centered Sovereign Agent Kernel: a self-owned modular-monolith runtime on NEXARA PRIME for turning human intent into bounded, auditable work.

The MVP is intentionally provider-free. It uses a deterministic mock model and does not depend on LangChain, AutoGen, CrewAI, or another third-party Agent framework as its core. A future provider adapter may be added behind `ModelGateway` without changing the kernel objects or state machine.

## MVP guarantees

- Human owns the mission, approval, pause, takeover, rollback, and safe-mode controls.
- MissionSpec, WorkContract, Plan, state transitions, tool invocations, evidence, memory patches, and evaluations are durable in SQLite.
- R0-R4 policy gates consequential actions; local report writes are approval-gated.
- Dynamic runtime roles are separate from visible personas.
- Writer Lease enforces one writer per resource.
- Every state transition emits an event and a state-transition evidence artifact.
- The acceptance flow runs with no API key and writes only under the project report root.

## Quick start

```bash
cd /Users/agentos/NEXARA-PRIME
./scripts/test_all.sh
./scripts/run_dev.sh
```

The API runs at `http://127.0.0.1:8765`; the local console is `ui/index.html` and reads `/api/runtime/overview` when served by a static server or API proxy.

## CLI demo

```bash
export PYTHONPATH="$PWD/src"
python3.12 -m nexara_prime.cli init
python3.12 -m nexara_prime.cli mission create "Read the local project materials and generate a verified report" --source-dir "$PWD/workspace/sample-project"
python3.12 -m nexara_prime.cli mission plan <MISSION_ID>
python3.12 -m nexara_prime.cli mission approve <MISSION_ID>
python3.12 -m nexara_prime.cli mission run <MISSION_ID>
python3.12 -m nexara_prime.cli mission status <MISSION_ID>
python3.12 -m nexara_prime.cli evidence list --mission-id <MISSION_ID>
python3.12 -m nexara_prime.cli memory inspect --mission-id <MISSION_ID>
python3.12 -m nexara_prime.cli eval run --mission-id <MISSION_ID>
```

## Architecture

The kernel is implemented in `src/nexara_prime/` as a modular monolith:

- `mission_compiler.py` and `contract_engine.py`: object-first mission compilation.
- `scheduler.py`, `capabilities.py`, and `token_compiler.py`: dynamic role and context loading.
- `state_machine.py`, `governance.py`, `tools.py`: execution and control boundaries.
- `events.py`, `evidence.py`, `memory.py`, `evaluation.py`: durable truth and replay.
- `model_gateway.py`: provider abstraction with deterministic mock provider.
- `runtime.py`: application service that coordinates the modules.
- `api.py` and `cli.py`: local API and operator surface.

See `docs/` for contracts, state transitions, governance, tool safety, memory, evaluation, and UI rules.

## Security boundary

The local runtime does not contact external systems by default, does not require secrets, does not push/merge/tag/deploy, and does not delete source files. Provider adapters are available but the default remains deterministic mock. File writes, commands, browser reads, output size, timeouts, idempotency, receipts, evidence, approvals, and recovery are bounded by the kernel. This is a hardened local runtime baseline; real production isolation, multi-user identity, and external browser connectors remain a later Gate.

## Hardening acceptance

Run `PYTHONPATH="$PWD/src" .venv/bin/python scripts/run_hardening_acceptance.py` to execute the real local project acceptance mission. Reports and evidence are written to `reports/production_hardening/`.
