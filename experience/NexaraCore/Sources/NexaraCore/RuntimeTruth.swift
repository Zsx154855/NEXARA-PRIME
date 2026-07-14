import Foundation

// MARK: - Runtime Truth Models (per Blueprint §9)

public struct Mission: Codable, Identifiable {
    public let missionId: String
    public let title: String
    public let objective: String
    public let state: MissionState
    public let riskLevel: RiskLevel
    public let contractId: String?
    public let planId: String?
    public let createdAt: String

    public var id: String { missionId }

    enum CodingKeys: String, CodingKey {
        case missionId = "mission_id"
        case title, objective, state
        case riskLevel = "risk_level"
        case contractId = "contract_id"
        case planId = "plan_id"
        case createdAt = "created_at"
    }
}

public enum MissionState: String, Codable {
    case draft = "DRAFT"
    case contextReady = "CONTEXT_READY"
    case contracted = "CONTRACTED"
    case planned = "PLANNED"
    case simulated = "SIMULATED"
    case approvalRequired = "APPROVAL_REQUIRED"
    case ready = "READY"
    case running = "RUNNING"
    case verifying = "VERIFYING"
    case completed = "COMPLETED"
    case paused = "PAUSED"
    case blocked = "BLOCKED"
    case failed = "FAILED"
    case rollingBack = "ROLLING_BACK"
    case rolledBack = "ROLLED_BACK"
    case cancelled = "CANCELLED"
}

public enum RiskLevel: String, Codable {
    case r0 = "R0"
    case r1 = "R1"
    case r2 = "R2"
    case r3 = "R3"
    case r4 = "R4"
}

public struct RuntimeOverview: Codable {
    public let missionsTotal: Int
    public let missionsActive: Int
    public let missionsCompleted: Int
    public let providersAvailable: [String]
    public let securityStatus: String
    public let hermesDependency: Int

    enum CodingKeys: String, CodingKey {
        case missionsTotal = "missions_total"
        case missionsActive = "missions_active"
        case missionsCompleted = "missions_completed"
        case providersAvailable = "providers_available"
        case securityStatus = "security_status"
        case hermesDependency = "hermes_dependency"
    }
}

public struct ExecutionStep: Codable, Identifiable {
    public let stepId: String
    public let title: String
    public let status: String
    public let role: String

    public var id: String { stepId }

    enum CodingKeys: String, CodingKey {
        case stepId = "step_id"
        case title, status, role
    }
}

public struct EvidenceReceipt: Codable, Identifiable {
    public let evidenceId: String
    public let claim: String
    public let confidence: Double
    public let verificationStatus: String

    public var id: String { evidenceId }

    enum CodingKeys: String, CodingKey {
        case evidenceId = "evidence_id"
        case claim, confidence
        case verificationStatus = "verification_status"
    }
}

// MARK: - Execution Mode (Runtime Truth)

public enum ExecutionMode: String {
    case mock = "mock"
    case dryRun = "dry_run"
    case local = "local"
    case live = "live"

    public var displayName: String {
        switch self {
        case .mock: "模拟 Mock"
        case .dryRun: "预演 Dry Run"
        case .local: "本地执行 Local"
        case .live: "外部执行 Live"
        }
    }

    public var icon: String {
        switch self {
        case .mock: "circle.dotted"
        case .dryRun: "rectangle.dashed"
        case .local: "desktopcomputer"
        case .live: "globe"
        }
    }
}
