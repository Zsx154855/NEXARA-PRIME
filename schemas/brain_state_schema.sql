-- NEXARA Memory Brain — brain_state.db schema
-- Phase 1: Memory Foundation (MemoryBrain + LongTermMemory)
-- Separate from runtime .nexara/store.db

CREATE TABLE IF NOT EXISTS brain_memories (
    memory_id TEXT PRIMARY KEY,
    mission_id TEXT NOT NULL DEFAULT 'global',
    key TEXT NOT NULL,
    content TEXT NOT NULL,
    kind TEXT NOT NULL,
    layer TEXT NOT NULL DEFAULT 'semantic',
    confidence REAL NOT NULL DEFAULT 1.0,
    decay_rate REAL NOT NULL DEFAULT 0.0,
    half_life_seconds INTEGER,
    evidence_id TEXT,
    provenance_chain TEXT,
    access_count INTEGER NOT NULL DEFAULT 0,
    last_accessed TEXT,
    consolidated_from TEXT,
    superseded_by TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT,
    UNIQUE(memory_id)
);

CREATE INDEX IF NOT EXISTS idx_brain_memories_mission ON brain_memories(mission_id);
CREATE INDEX IF NOT EXISTS idx_brain_memories_kind ON brain_memories(kind);
CREATE INDEX IF NOT EXISTS idx_brain_memories_layer ON brain_memories(layer);
CREATE INDEX IF NOT EXISTS idx_brain_memories_key ON brain_memories(key);
CREATE INDEX IF NOT EXISTS idx_brain_memories_status ON brain_memories(status);

CREATE TABLE IF NOT EXISTS memory_decay_state (
    kind TEXT PRIMARY KEY,
    half_life_seconds INTEGER NOT NULL,
    min_confidence REAL NOT NULL DEFAULT 0.1,
    decay_function TEXT NOT NULL DEFAULT 'exponential',
    last_tick TEXT,
    updated_at TEXT NOT NULL
);

INSERT OR IGNORE INTO memory_decay_state(kind, half_life_seconds, min_confidence) VALUES
    ('short_term', 3600, 0.1),
    ('temporary_context', 86400, 0.1),
    ('unverified_inference', 1800, 0.05),
    ('fact', 7776000, 0.3),
    ('user_fact', 15552000, 0.5),
    ('project_fact', 31536000, 0.5),
    ('preference', 7776000, 0.3),
    ('decision', 0, 0.9),
    ('failure', 0, 0.9),
    ('failure_experience', 15552000, 0.3),
    ('patch', 0, 0.9),
    ('skill_improvement', 0, 0.9),
    ('system_rule', 0, 0.9);

CREATE TABLE IF NOT EXISTS memory_consolidation_log (
    log_id TEXT PRIMARY KEY,
    source_memory_id TEXT NOT NULL,
    target_memory_id TEXT NOT NULL,
    from_layer TEXT NOT NULL,
    to_layer TEXT NOT NULL,
    trigger TEXT NOT NULL,
    reason TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memory_access_log (
    log_id TEXT PRIMARY KEY,
    memory_id TEXT NOT NULL,
    accessed_at TEXT NOT NULL,
    query TEXT,
    access_type TEXT NOT NULL DEFAULT 'recall'
);

CREATE INDEX IF NOT EXISTS idx_access_log_memory ON memory_access_log(memory_id);

CREATE TABLE IF NOT EXISTS memory_health_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    total_memories INTEGER NOT NULL DEFAULT 0,
    active_count INTEGER NOT NULL DEFAULT 0,
    stale_count INTEGER NOT NULL DEFAULT 0,
    archived_count INTEGER NOT NULL DEFAULT 0,
    coverage_score REAL NOT NULL DEFAULT 0.0,
    freshness_score REAL NOT NULL DEFAULT 0.0,
    consistency_score REAL NOT NULL DEFAULT 0.0,
    layer_distribution TEXT NOT NULL DEFAULT '{}',
    kind_distribution TEXT NOT NULL DEFAULT '{}',
    taken_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memory_provenance_chain (
    provenance_id TEXT PRIMARY KEY,
    memory_id TEXT NOT NULL,
    evidence_id TEXT NOT NULL,
    source_file TEXT,
    commit_sha TEXT,
    trace_id TEXT,
    recorded_at TEXT NOT NULL,
    UNIQUE(memory_id)
);

CREATE INDEX IF NOT EXISTS idx_provenance_memory ON memory_provenance_chain(memory_id);
CREATE INDEX IF NOT EXISTS idx_provenance_evidence ON memory_provenance_chain(evidence_id);
