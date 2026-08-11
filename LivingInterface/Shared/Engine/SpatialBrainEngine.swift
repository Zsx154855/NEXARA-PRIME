import SwiftUI
import Combine

// ── Spatial Brain Engine V2: 空间化主脑 ──
// Transforms the flat 2D panel into a spatial NEXARA Space:
// - Center: liquid life core (the brain)
// - Orbiting: memory galaxies, mission trajectories, learning nodes
// - Always visible: Human Control Plane (pause, approve, reject, modify)
// - Camera: subtle parallax and orbital drift

@MainActor
final class SpatialBrainEngine: ObservableObject {
    // ── Published State ──
    @Published var camera: SpatialCamera = .default
    @Published var corePosition: CGPoint = .zero
    @Published var memoryNodes: [MemoryNode] = []
    @Published var missionOrbits: [MissionOrbit] = []
    @Published var learningNodes: [LearningNode] = []
    @Published var controlPlane: ControlPlaneState = .default
    @Published var spatialLayout: SpatialLayout = .default
    @Published var isHumanControlProminent: Bool = false

    // ── Configuration ──
    private let galaxyRadius: Double = 180
    private let missionOrbitRadius: Double = 140
    private let learningClusterRadius: Double = 160

    // ── Internal ──
    private var timer: Timer?
    private var cancellables = Set<AnyCancellable>()
    private var time: Double = 0

    // MARK: - Lifecycle

    init() {
        initializeMemoryNodes()
        initializeMissionOrbits()
        initializeLearningNodes()
        startSpatialLoop()
    }

    // MARK: - Layout Update

    func applyLayout(_ layout: SpatialLayout) {
        withAnimation(.easeInOut(duration: 1.0)) {
            spatialLayout = layout
            isHumanControlProminent = layout.controlPlanePosition > 0.8
        }
    }

    // MARK: - Spatial Loop

    private func startSpatialLoop() {
        timer = Timer.scheduledTimer(withTimeInterval: 0.05, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.updateSpatialFrame()
            }
        }
    }

    private func updateSpatialFrame() {
        time += 0.05

        // Subtle camera drift
        let driftX = sin(time * 0.15) * 6.0
        let driftY = cos(time * 0.2) * 4.0
        camera = SpatialCamera(
            offsetX: driftX, offsetY: driftY,
            zoom: 1.0 + sin(time * 0.08) * 0.03,
            rotation: sin(time * 0.05) * 0.02
        )

        // Orbit memory nodes
        for i in 0..<memoryNodes.count {
            memoryNodes[i].angle += memoryNodes[i].orbitSpeed * 0.05 * spatialLayout.memoryVisibility
            memoryNodes[i].opacity = spatialLayout.memoryVisibility * memoryNodes[i].baseOpacity
        }

        // Orbit missions
        for i in 0..<missionOrbits.count {
            missionOrbits[i].angle += missionOrbits[i].orbitSpeed * 0.05 * spatialLayout.missionVisibility
            missionOrbits[i].opacity = spatialLayout.missionVisibility * missionOrbits[i].baseOpacity
        }

        // Pulse learning nodes
        for i in 0..<learningNodes.count {
            learningNodes[i].pulsePhase += learningNodes[i].growthRate * 0.05 * spatialLayout.learningVisibility
            learningNodes[i].opacity = spatialLayout.learningVisibility * learningNodes[i].baseOpacity
        }

        // Control plane prominence
        controlPlane.scale = 0.9 + spatialLayout.controlPlanePosition * 0.3
    }

    // MARK: - Initialization

    private func initializeMemoryNodes() {
        let count = 6
        memoryNodes = (0..<count).map { i in
            let seed = Double(i) / Double(count)
            let angle = seed * .pi * 2
            return MemoryNode(
                id: "memory-\(i)",
                label: memoryLabels[i % memoryLabels.count],
                angle: angle,
                orbitRadius: galaxyRadius * (0.6 + seed * 0.4),
                orbitSpeed: 0.2 + seed * 0.5,
                baseOpacity: 0.6 + seed * 0.4,
                opacity: 0,
                size: 20 + seed * 16
            )
        }
    }

    private func initializeMissionOrbits() {
        let count = 5
        missionOrbits = (0..<count).map { i in
            let seed = Double(i) / Double(count)
            let angle = seed * .pi * 2 + .pi / Double(count)
            return MissionOrbit(
                id: "mission-\(i)",
                label: missionLabels[i % missionLabels.count],
                angle: angle,
                orbitRadius: missionOrbitRadius * (0.7 + seed * 0.3),
                orbitSpeed: 0.3 + seed * 0.6,
                baseOpacity: 0.5 + seed * 0.5,
                opacity: 0,
                trailLength: 3 + Int(seed * 4)
            )
        }
    }

    private func initializeLearningNodes() {
        let count = 8
        learningNodes = (0..<count).map { i in
            let seed = Double(i) / Double(count)
            let angle = seed * .pi * 2
            return LearningNode(
                id: "learn-\(i)",
                label: learningLabels[i % learningLabels.count],
                angle: angle,
                orbitRadius: learningClusterRadius * (0.5 + seed * 0.5),
                pulsePhase: seed * .pi * 2,
                growthRate: 0.3 + seed * 0.7,
                baseOpacity: 0.4 + seed * 0.6,
                opacity: 0,
                nodeSize: 6 + seed * 10
            )
        }
    }

    // MARK: - Memory Galaxy

    struct MemoryNode: Identifiable, Sendable {
        let id: String
        let label: String
        var angle: Double
        let orbitRadius: Double
        let orbitSpeed: Double
        let baseOpacity: Double
        var opacity: Double
        let size: Double

        func position(center: CGPoint) -> CGPoint {
            CGPoint(
                x: center.x + cos(angle) * orbitRadius,
                y: center.y + sin(angle) * orbitRadius
            )
        }
    }

    struct MissionOrbit: Identifiable, Sendable {
        let id: String
        let label: String
        var angle: Double
        let orbitRadius: Double
        let orbitSpeed: Double
        let baseOpacity: Double
        var opacity: Double
        let trailLength: Int

        func position(center: CGPoint) -> CGPoint {
            CGPoint(
                x: center.x + cos(angle) * orbitRadius,
                y: center.y + sin(angle) * orbitRadius
            )
        }

        func trailPositions(center: CGPoint) -> [CGPoint] {
            (0..<trailLength).map { i in
                let offset = Double(i + 1) * 0.12
                let a = angle - offset
                return CGPoint(
                    x: center.x + cos(a) * orbitRadius,
                    y: center.y + sin(a) * orbitRadius
                )
            }
        }
    }

    struct LearningNode: Identifiable, Sendable {
        let id: String
        let label: String
        var angle: Double
        let orbitRadius: Double
        var pulsePhase: Double
        let growthRate: Double
        let baseOpacity: Double
        var opacity: Double
        let nodeSize: Double

        func position(center: CGPoint) -> CGPoint {
            CGPoint(
                x: center.x + cos(angle) * orbitRadius,
                y: center.y + sin(angle) * orbitRadius
            )
        }

        var pulseScale: Double {
            1.0 + sin(pulsePhase) * 0.3
        }
    }

    struct SpatialCamera: Sendable {
        var offsetX: Double
        var offsetY: Double
        var zoom: Double
        var rotation: Double

        static let `default` = SpatialCamera(
            offsetX: 0, offsetY: 0, zoom: 1.0, rotation: 0
        )
    }

    struct ControlPlaneState: Sendable {
        var scale: Double
        var glowIntensity: Double
        var pulseActive: Bool

        static let `default` = ControlPlaneState(
            scale: 1.0, glowIntensity: 0.5, pulseActive: false
        )
    }

    // ── Labels ──
    private let memoryLabels = ["长期记忆", "工作记忆", "情景记忆", "语义记忆", "程序记忆", "感知记忆"]
    private let missionLabels = ["当前任务", "任务队列", "已完成", "分析中", "等待审批"]
    private let learningLabels = ["模式识别", "知识图谱", "规则提取", "概念形成", "关联学习", "迁移学习", "强化学习", "对比学习"]

    deinit {
        timer?.invalidate()
    }
}
