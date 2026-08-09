# NEXARA Control Plane — Product UI Truth

> Generated: 2026-08-09 | Phase 13 Product Architecture Design

## Reality Baseline

| Field | Value |
|-------|-------|
| Branch | `feat/brand-baihan` |
| HEAD | `ceae37f` — "fix: timeout transition EXECUTION->FAILED (not EXECUTION->CANCELLED)" |
| Worktree | CLEAN |
| Core Freeze | FROZEN @ `8a75910` (7/7 gates) |
| Runtime Seal | SEALED @ `ceae37f` (R1-R10 + F1/F2) |
| Test Baseline | 2044/2044 PASS |
| Python | 3.12.13 |
| Governance | NSEC V2.1 (19 chapters, 55 articles) |

## Runtime API Surface (Current)

### Mission CRUD
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/missions` | List all missions |
| POST | `/api/missions` | Create mission |
| GET | `/api/missions/{id}` | Mission detail (inspect_mission) |
| POST | `/api/missions/{id}/plan` | Generate plan |
| POST | `/api/missions/{id}/approve` | Approve/reject |
| POST | `/api/missions/{id}/run` | Execute mission |
| POST | `/api/missions/{id}/pause` | Pause mission |
| POST | `/api/missions/{id}/resume` | Resume mission |
| POST | `/api/missions/{id}/rollback` | Rollback |
| POST | `/api/missions/{id}/safe-mode` | Toggle safe mode |

### Evidence & Tools
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/evidence` | List evidence (optional mission_id) |
| GET | `/api/receipts` | Verify receipt chain |
| GET | `/api/tools` | List tool invocations |
| GET | `/api/missions/{id}/tools` | Per-mission tools |
| GET | `/api/memory` | Inspect memory |
| GET | `/api/memory/candidates` | Memory patch candidates |

### Governance
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/approvals` | List approvals |
| GET | `/api/events/{id}` | Event replay |
| POST | `/api/recovery/check` | Recovery check |

### Adaptive Runtime
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/adaptive/status` | Runtime status |
| GET | `/adaptive/missions/{id}` | Adaptive mission view |
| GET | `/adaptive/missions/{id}/explain` | Decision explanation |
| GET | `/adaptive/missions/{id}/budget` | Budget/usage |
| GET | `/adaptive/missions/{id}/agents` | Agent assignments |
| GET | `/adaptive/missions/{id}/routing` | Model routing |

### Overview & Health
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Health check |
| GET | `/api/runtime/overview` | Full dashboard snapshot |
| GET | `/api/knowledge-universe` | Knowledge vault |

### inspect_mission Returns
`mission_id`, `state`, `risk_level`, `spec`, `plan`, `title`, `objective`,
`created_at`, `updated_at`, `provider`, `provider_unavailable`,
`approval_status`, `pending_action`, `evidence_count`, `latest_evidence`,
`receipt_status`, `memory_patch_status`, `evaluation_status`,
`retry_count`, `recovery_pointer`, `terminal_reason`,
`paused`, `safe_mode`, `trace_id`

### overview Returns
`system` (name, mode, healthy, human_control, mock_default, adapters),
`missions` (last 20), `approvals` (last 20), `evidence` (last 20),
`tools` (last 20), `capabilities`, `recovery`

### Existing UI Mount Points (api.py:218-230)
- `/console` → `ui/out/` (Next.js static export)
- `/knowledge-universe` → `ui/knowledge-universe/`
- `/runtime-truth` → `ui/runtime-truth/`

## Design Constraints

1. **No new Runtime features** — Control Plane is read-only governance UI
2. **No database direct access** — All data through Runtime API
3. **No state mutation from UI** — Except approve/reject/pause/resume/rollback
4. **Apple-level product quality** — Professional, calm, enterprise, human-centered
5. **No AI-HUD / cyberpunk / robot aesthetic** — Clean enterprise dashboard
