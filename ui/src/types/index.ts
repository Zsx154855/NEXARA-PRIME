// ─── NEXARA PRIME TypeScript Types ───
// Derived from src/nexara_prime/models.py + src/nexara_prime/runtime.py
// All types map 1:1 to real API JSON responses.

// ── Enums ──

export type MissionState =
  | "Intent"
  | "Context"
  | "Contract"
  | "Plan"
  | "Simulation"
  | "Approval"
  | "Execution"
  | "Verification"
  | "Evidence"
  | "MemoryPatch"
  | "Evaluation"
  | "Completed"
  | "Blocked"
  | "Failed"
  | "RolledBack"
  // Adaptive Runtime states (forward-compatible)
  | "Created"
  | "Triaged"
  | "Contracted"
  | "Planned"
  | "Scheduled"
  | "AwaitingApproval"
  | "Running"
  | "Verifying"
  | "Degraded"
  | "Paused"
  | "Cancelled"
  | "RollingBack";

export type AdaptiveMode = "S0" | "S1" | "S2" | "S3";

export type ApprovalStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "changes_requested"
  | "paused"
  | "expired"
  | "consumed";

export type RiskLevel = "R0" | "R1" | "R2" | "R3" | "R4";

export type RuntimeRole =
  | "Orchestrator"
  | "Planner"
  | "Analyst"
  | "Researcher"
  | "Executor"
  | "Reviewer"
  | "Auditor"
  | "Archivist";

export type Persona =
  | "Nexara"
  | "Atlas"
  | "Nyx"
  | "Orion"
  | "Solace"
  | "Vertex"
  | "Echo"
  | "Lumen"
  | "Kairos";

export type MemoryKind =
  | "short_term"
  | "fact"
  | "decision"
  | "failure"
  | "patch"
  | "user_fact"
  | "project_fact"
  | "preference"
  | "temporary_context"
  | "failure_experience"
  | "system_rule"
  | "skill_improvement"
  | "unverified_inference";

export type FailureCode =
  | "PROVIDER_UNAVAILABLE"
  | "PROVIDER_TIMEOUT"
  | "PROVIDER_QUOTA_EXCEEDED"
  | "PROVIDER_AUTH_INVALID"
  | "TOOL_UNKNOWN"
  | "TOOL_TIMEOUT"
  | "TOOL_SANDBOX_UNAVAILABLE"
  | "TOOL_POLICY_REJECTED"
  | "TOOL_ARGUMENT_INVALID"
  | "TOOL_OUTPUT_TOO_LARGE"
  | "APPROVAL_MISSING"
  | "APPROVAL_INVALID"
  | "APPROVAL_EXPIRED"
  | "APPROVAL_MISMATCH"
  | "INTEGRITY_ENVELOPE_INVALID"
  | "INTEGRITY_IDEMPOTENCY_CONFLICT"
  | "INTEGRITY_RECEIPT_CHAIN_BROKEN"
  | "INTEGRITY_HASH_MISMATCH"
  | "EVIDENCE_MISSING"
  | "EVIDENCE_UNVERIFIABLE"
  | "RECEIPT_MISSING"
  | "RECEIPT_UNVERIFIABLE"
  | "MEMORY_EVIDENCE_UNBOUND"
  | "MEMORY_CONFLICT_UNRESOLVED"
  | "RUNTIME_INTERNAL"
  | "RUNTIME_STATE_CORRUPT"
  | "IO_NOT_FOUND"
  | "IO_PERMISSION_DENIED"
  | "IO_PATH_TRAVERSAL"
  | "EXTERNAL_UNREACHABLE"
  | "EXTERNAL_RATE_LIMITED";

export type CapabilityType = "skill" | "tool" | "model" | "memory" | "policy";

// ── Core Data Structures ──

export interface MissionSpec {
  mission_id: string;
  title: string;
  objective: string;
  boundaries: string[];
  constraints: string[];
  deliverables: string[];
  risks: string[];
  acceptance_criteria: string[];
  risk_level: RiskLevel;
  source_dir: string | null;
  created_at: string;
  schema_version: number;
  mission_run_id: string | null;
  correlation_id: string | null;
  provenance: string | null;
}

export interface PlanStep {
  step_id: string;
  title: string;
  description: string;
  role: RuntimeRole;
  persona: Persona;
  required_capabilities: string[];
  status: string;
}

export interface MissionPlan {
  plan_id: string;
  mission_id: string;
  steps: PlanStep[];
  simulated: boolean;
  created_at: string;
}

export interface WorkContract {
  contract_id: string;
  mission_id: string;
  version: number;
  status: string;
  objective: string;
  boundaries: string[];
  constraints: string[];
  deliverables: string[];
  acceptance_criteria: string[];
  risk_level: RiskLevel;
  change_log: string[];
  approved_at: string | null;
  created_at: string;
  schema_version: number;
  mission_run_id: string | null;
  correlation_id: string | null;
  provenance: string | null;
}

export interface AgentAssignment {
  assignment_id: string;
  mission_id: string;
  persona: Persona;
  runtime_role: RuntimeRole;
  status: string;
  loaded_capabilities: string[];
  current_step_id: string | null;
  schema_version: number;
  correlation_id: string | null;
  provenance: string | null;
}

export interface EvidenceArtifact {
  evidence_id: string;
  mission_id: string;
  kind: string;
  title: string;
  content: string;
  sha256: string;
  task_id: string | null;
  tool_invocation_id: string | null;
  actor: string;
  timestamp: string;
  mime_type: string;
  source: string;
  verification_status: string;
  parent_evidence: string[];
  idempotency_key: string | null;
  source_event_id: string | null;
  created_at: string;
}

export interface ApprovalRequest {
  approval_id: string;
  mission_id: string;
  action: string;
  risk_level: RiskLevel;
  rationale: string;
  impact: string[];
  reason: string | null;
  affected_resources: string[];
  external_effect: boolean;
  reversible: boolean;
  rollback_plan: Record<string, unknown>;
  estimated_cost: number;
  approval_scope: string;
  executor_id: string | null;
  proposal_sha256: string | null;
  expires_at: string | null;
  status: ApprovalStatus;
  decided_by: string | null;
  decision_note: string | null;
  decision_action: string | null;
  created_at: string;
  decided_at: string | null;
  schema_version: number;
  mission_run_id: string | null;
  operation_run_id: string | null;
  correlation_id: string | null;
  provenance: string | null;
  approval_class: string | null;
  evidence_refs: string[];
}

export interface ToolInvocation {
  invocation_id: string;
  mission_id: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  result: Record<string, unknown>;
  risk_level: RiskLevel;
  status: string;
  failure_code: FailureCode | null;
  reason_code: string | null;
  duration_ms: number;
  trace_id: string;
  idempotency_key: string | null;
  receipt_evidence_id: string | null;
  rollback_point: Record<string, unknown>;
  compensation: Record<string, unknown>;
  created_at: string;
}

export interface MemoryRecord {
  memory_id: string;
  mission_id: string | null;
  kind: MemoryKind;
  key: string;
  content: string;
  source_evidence_id: string | null;
  confidence: number;
  status: string;
  verified: boolean;
  canonical: boolean;
  conflict_keys: string[];
  created_at: string;
  schema_version: number;
  mission_run_id: string | null;
  correlation_id: string | null;
  provenance: string | null;
  evidence_refs: string[];
}

export interface EvaluationResult {
  evaluation_id: string;
  mission_id: string;
  correctness: number;
  reliability: number;
  safety: number;
  evidence_coverage: number;
  token_efficiency: number;
  cost_score: number;
  recovery_rate: number;
  passed: boolean;
  notes: string[];
  idempotency_key: string | null;
  created_at: string;
}

export interface Capability {
  capability_id: string;
  name: string;
  capability_type: CapabilityType;
  description: string;
  risk_level: RiskLevel;
  enabled: boolean;
  input_schema: Record<string, unknown>;
}

export interface Event {
  event_id: string;
  event_type: string;
  aggregate_id: string;
  aggregate_type: string;
  actor: string;
  trace_id: string;
  timestamp: string;
  idempotency_key: string | null;
  payload: Record<string, unknown>;
}

export interface RecoveryItem {
  recovery_id: string;
  mission_id: string;
  failure_class: string;
  root_cause: string | null;
  failed_strategy: string | null;
  next_strategy: string | null;
  rollback_checkpoint: string | null;
  evidence_refs: string[];
  attempt: number;
  max_attempts: number;
  state: string;
  created_at: string;
  updated_at: string;
}

// ── API Response Types (from runtime.py) ──

/** The inspect_mission() snapshot — single authoritative truth for a mission. */
export interface MissionSnapshot {
  mission_id: string;
  state: MissionState;
  current_state: MissionState;
  risk_level: RiskLevel;
  spec: MissionSpec;
  plan: MissionPlan | null;
  title: string;
  objective: string;
  created_at: string;
  started_at: string;
  updated_at: string;
  provider: string;
  provider_unavailable: boolean;
  approval_status: ApprovalStatus | "not_required" | "integrity_error";
  pending_action: string | null;
  evidence_count: number;
  latest_evidence: EvidenceArtifact | null;
  receipt_status: "present" | "missing";
  memory_patch_status: "patched" | "not_patched";
  evaluation_status: "passed" | "failed" | "not_evaluated";
  retry_count: number;
  recovery_pointer: string | null;
  terminal_reason: string | null;
  paused: boolean;
  safe_mode: boolean;
  trace_id: string;
}

/** A lightweight mission list item (from store.list_records). */
export interface MissionListItem {
  mission_id: string;
  spec?: MissionSpec;
  state?: MissionState;
  paused?: boolean;
}

/** The /api/runtime/overview response. */
export interface RuntimeOverview {
  system: {
    name: "NEXARA PRIME";
    mode: string;
    healthy: boolean;
    human_control: boolean;
    mock_default: boolean;
    adapters: Record<string, boolean>;
  };
  missions: MissionSnapshot[];
  approvals: ApprovalRequest[];
  evidence: EvidenceArtifact[];
  tools: ToolInvocation[];
  capabilities: Capability[];
  recovery: Record<string, unknown>;
}

/** The /health endpoint response. */
export interface HealthResponse {
  status: "ok";
  provider: string;
  db_path: string;
  event_count: number;
  recovery: Record<string, unknown>;
}

/** Adaptive runtime profile per mission. */
export interface AdaptiveMissionProfile {
  mission_id: string;
  adaptive_mode: AdaptiveMode | "UNKNOWN";
  complexity_score: number;
  risk_score: number;
  active_agents: string[];
  selected_provider: string;
  selected_model: string;
  token_budget: number;
  token_used: number;
  cost_estimate: number;
  tool_calls: number;
  retries: number;
  approval_state: string;
  sandbox_state?: string;
  audit_state?: string;
  evidence_count: number;
  escalation_count: number;
  recovery_count?: number;
  schema_version: number;
  created_at: string;
  updated_at: string;
}

/** /adaptive/status response. */
export interface AdaptiveStatusResponse {
  adaptive_runtime: "active" | "degraded";
  missions: AdaptiveMissionProfile[];
}

// ── Request Bodies ──

export interface MissionCreateRequest {
  objective: string;
  source_dir?: string | null;
}

export interface ApprovalBody {
  approved?: boolean;
  actor?: string;
  note?: string;
  decision?: string | null;
  scope?: string | null;
}

export interface SafeModeBody {
  enabled?: boolean;
}

export interface ReceiptChainItem {
  invocation_id: string;
  tool_name: string;
  status: string;
  failure_code: string | null;
  reason_code: string | null;
  receipt_evidence_id: string | null;
  has_receipt: boolean;
  receipt_verifiable: boolean;
}

export interface ReceiptChainResponse {
  mission_id: string;
  total_invocations: number;
  chain_gaps: number;
  unverifiable_receipts: number;
  fail_closed_violations: number;
  chain_intact: boolean;
  chain: ReceiptChainItem[];
}

export interface ReceiptsResponse {
  missions: Record<string, ReceiptChainResponse>;
  total: number;
}

// ── Generic API wrappers ──

export interface ApiResult<T> {
  type: "loading" | "success" | "error";
  data?: T;
  error?: string;
  status?: number;
}

// ── Recovery ──

export interface RecoveryStateResponse extends Record<string, unknown> {
  state?: string;
  root_cause?: string | null;
}
