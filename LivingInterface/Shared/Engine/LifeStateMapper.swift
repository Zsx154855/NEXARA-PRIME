import SwiftUI

// ── Life State Mapper V2: 状态驱动视觉系统 ──
// Maps internal agent state to visual parameters for all engines.
// Inputs: task status, execution state, memory state, learning state,
//         risk state, user control state
// Outputs: breath speed, fluid velocity, glow intensity, particle density,
//          core morphology, spatial layout

@MainActor
final class LifeStateMapper: ObservableObject {
    // ── Input State ──
    @Published var currentTaskStatus: TaskStatus = .idle
    @Published var executionPhase: ExecutionPhase = .none
    @Published var memoryActivity: MemoryActivity = .dormant
    @Published var learningActivity: LearningActivity = .idle
    @Published var riskLevel: RiskLevel = .none
    @Published var userControlState: UserControlState = .free

    // ── Output Visual State ──
    @Published var livingState: LivingState = .silent
    @Published var liquidTarget: LiquidCoreState = .silent
    @Published var spatialLayout: SpatialLayout = .default
    @Published var glowProfile: GlowProfile = .calm

    // ── Mappings ──

    func recompute() {
        livingState = computeLivingState()
        liquidTarget = computeLiquidTarget()
        spatialLayout = computeSpatialLayout()
        glowProfile = computeGlowProfile()
    }

    // MARK: - State Computation

    private func computeLivingState() -> LivingState {
        switch userControlState {
        case .awaitingApproval:
            return .awaitingApproval
        case .paused:
            return .silent
        case .free, .active:
            break
        }

        if riskLevel >= .high {
            return .awaitingApproval
        }

        switch (currentTaskStatus, executionPhase) {
        case (.executing, _), (_, .running):
            return .executing
        case (.analyzing, _):
            return .thinking
        case (.learning, _):
            return .learning
        case (.idle, .none):
            if memoryActivity != .dormant { return .thinking }
            if learningActivity != .idle { return .learning }
            return .silent
        case (_, _):
            return .silent
        }
    }

    private func computeLiquidTarget() -> LiquidCoreState {
        switch livingState {
        case .silent:            return .silent
        case .thinking:          return .thinking
        case .planning:          return .planning
        case .executing:         return .executing
        case .learning:          return .learning
        case .awaitingApproval:  return .awaitingApproval
        case .recovery:          return .recovery
        }
    }

    private func computeSpatialLayout() -> SpatialLayout {
        switch livingState {
        case .silent:
            return SpatialLayout(
                coreScale: 0.8, orbitSpread: 0.5,
                memoryVisibility: 0.4, missionVisibility: 0.2,
                learningVisibility: 0.3, controlPlanePosition: 0.8
            )
        case .thinking:
            return SpatialLayout(
                coreScale: 1.0, orbitSpread: 0.3,
                memoryVisibility: 0.8, missionVisibility: 0.3,
                learningVisibility: 0.5, controlPlanePosition: 0.7
            )
        case .executing:
            return SpatialLayout(
                coreScale: 1.2, orbitSpread: 0.7,
                memoryVisibility: 0.5, missionVisibility: 1.0,
                learningVisibility: 0.4, controlPlanePosition: 0.6
            )
        case .learning:
            return SpatialLayout(
                coreScale: 1.0, orbitSpread: 0.6,
                memoryVisibility: 0.6, missionVisibility: 0.3,
                learningVisibility: 1.0, controlPlanePosition: 0.7
            )
        case .awaitingApproval:
            return SpatialLayout(
                coreScale: 0.9, orbitSpread: 0.4,
                memoryVisibility: 0.3, missionVisibility: 0.1,
                learningVisibility: 0.2, controlPlanePosition: 0.95
            )
        case .planning:
            return SpatialLayout(
                coreScale: 0.95, orbitSpread: 0.4,
                memoryVisibility: 0.7, missionVisibility: 0.5,
                learningVisibility: 0.4, controlPlanePosition: 0.75
            )
        case .recovery:
            return SpatialLayout(
                coreScale: 0.85, orbitSpread: 0.3,
                memoryVisibility: 0.5, missionVisibility: 0.2,
                learningVisibility: 0.3, controlPlanePosition: 0.85
            )
        }
    }

    private func computeGlowProfile() -> GlowProfile {
        let baseIntensity: Double
        switch livingState {
        case .silent:            baseIntensity = 0.3
        case .thinking:          baseIntensity = 0.6
        case .planning:          baseIntensity = 0.55
        case .executing:         baseIntensity = 0.8
        case .learning:          baseIntensity = 0.5
        case .awaitingApproval:  baseIntensity = 0.9
        case .recovery:          baseIntensity = 0.45
        }

        return GlowProfile(
            intensity: baseIntensity * (riskLevel >= .medium ? 1.3 : 1.0),
            pulseSpeed: livingState == .awaitingApproval ? 1.5 : 1.0,
            warmth: livingState == .awaitingApproval ? 0.8 : 0.5,
            radiusMultiplier: 1.0
        )
    }
}

// MARK: - Input Enums

enum TaskStatus: String, Sendable {
    case idle = "空闲"
    case analyzing = "分析中"
    case executing = "执行中"
    case learning = "学习中"
}

enum ExecutionPhase: String, Sendable {
    case none = "无"
    case preparing = "准备中"
    case running = "运行中"
    case validating = "验证中"
    case complete = "完成"
}

enum MemoryActivity: String, Sendable {
    case dormant = "休眠"
    case recalling = "回忆中"
    case consolidating = "整合中"
    case evolving = "进化中"
}

enum LearningActivity: String, Sendable {
    case idle = "空闲"
    case observing = "观察中"
    case extracting = "提取模式"
    case integrating = "整合中"
}

enum RiskLevel: Int, Comparable, Sendable {
    case none = 0
    case low = 1
    case medium = 2
    case high = 3
    case critical = 4

    static func < (lhs: RiskLevel, rhs: RiskLevel) -> Bool {
        lhs.rawValue < rhs.rawValue
    }
}

enum UserControlState: String, Sendable {
    case free = "自由"
    case active = "活跃"
    case paused = "暂停"
    case awaitingApproval = "等待审批"
}

// MARK: - Output Models

struct SpatialLayout: Sendable {
    var coreScale: Double            // 0.5–2.0
    var orbitSpread: Double          // 0.0 (tight) – 1.0 (wide)
    var memoryVisibility: Double     // 0.0–1.0
    var missionVisibility: Double    // 0.0–1.0
    var learningVisibility: Double   // 0.0–1.0
    var controlPlanePosition: Double // 0.0 (far) – 1.0 (prominent)

    static let `default` = SpatialLayout(
        coreScale: 1.0, orbitSpread: 0.5,
        memoryVisibility: 0.6, missionVisibility: 0.4,
        learningVisibility: 0.4, controlPlanePosition: 0.7
    )
}

struct GlowProfile: Sendable {
    var intensity: Double       // 0.0–1.0
    var pulseSpeed: Double      // multiplier
    var warmth: Double          // 0.0 (cool) – 1.0 (warm)
    var radiusMultiplier: Double

    static let calm = GlowProfile(
        intensity: 0.3, pulseSpeed: 1.0,
        warmth: 0.5, radiusMultiplier: 1.0
    )
}
