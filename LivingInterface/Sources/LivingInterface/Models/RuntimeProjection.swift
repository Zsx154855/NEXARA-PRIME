import Foundation

// MARK: - Runtime Projection Models

struct IdentitySnapshot: Codable, Identifiable {
    var id: String { fingerprint }
    let fingerprint: String
    let name: String
    let ownerId: String
    let soulStatus: SoulIntegrity
    let createdAt: String
}

struct SoulIntegrity: Codable {
    let immutableCount: Int
    let stableCount: Int
    let integrityVerified: Bool
    let lastVerifiedAt: String
}

struct MissionSummary: Codable, Identifiable {
    var id: String { missionId }
    let missionId: String
    let objective: String
    let state: String
    let riskLevel: String
    let createdAt: String
}

struct ApprovalRequest: Codable, Identifiable {
    var id: String { approvalId }
    let approvalId: String
    let missionId: String
    let riskLevel: String
    let scope: [String]
    let status: String
    let createdAt: String
}

struct EvidenceSummary: Codable, Identifiable {
    var id: String { evidenceId }
    let evidenceId: String
    let missionId: String
    let sha256: String
    let verified: Bool
    let createdAt: String
}

struct MemoryCategory: Codable, Identifiable {
    var id: String { category }
    let category: String
    let count: Int
    let records: [MemoryRecord]
}

struct MemoryRecord: Codable, Identifiable {
    var id: String { memoryId }
    let memoryId: String
    let key: String
    let kind: String
    let sourceEvidenceId: String?
    let content: String
    let deletable: Bool
    let createdAt: String
}

struct RuntimeHealth: Codable {
    let uptime: Double
    let providerStatus: [String: String]
    let circuitBreaker: [String: Bool]
    let activeMissions: Int
    let lastRestartAt: String?
}

enum ConnectionStatus: String, Codable {
    case connecting
    case connected
    case degraded
    case disconnected
    case recovering
}

struct RuntimeProjection: Codable {
    var identity: IdentitySnapshot?
    var missions: [MissionSummary] = []
    var approvals: [ApprovalRequest] = []
    var evidence: [EvidenceSummary] = []
    var memory: [MemoryCategory] = []
    var health: RuntimeHealth?
    var connection: ConnectionStatus = .disconnected
}
