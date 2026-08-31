import SwiftUI
import Combine

// ── Living Engine V2: NEXARA Living Core Visual Engine ──
// Integrates: LiquidCoreEngine, LifeStateMapper, AudioResonanceEngine,
// SpatialBrainEngine, SkinEngine for the full V2 living interface.

@MainActor
final class LivingEngine: ObservableObject {
    // ── Core State ──
    @Published var state: LivingState = .silent
    @Published var breathPhase: Double = 0.0
    @Published var isReducedMotion: Bool = false
    @Published var microphoneEnabled: Bool = false

    // ── Human Control State ──
    @Published var humanControlPaused: Bool = false
    @Published var pendingApprovalCount: Int = 0
    @Published var currentTask: String?
    @Published var currentGoal: String?
    @Published var recentLearnings: [String] = []

    // ── V2 Sub-Engines ──
    let skinEngine = SkinEngine()
    let liquidCore = LiquidCoreEngine()
    let stateMapper = LifeStateMapper()
    let audioResonance = AudioResonanceEngine()
    let spatialBrain = SpatialBrainEngine()

    // ── Internal ──
    private var timer: Timer?
    private var cancellables = Set<AnyCancellable>()

    var currentSkin: LifeSkin { skinEngine.activeSkin }
    var skinProfile: SkinProfile { skinEngine.profile(for: currentSkin) }
    var audioReactive: Bool { state == .executing || state == .learning }

    init() {
        startBreathCycle()
        observeReduceMotion()
        observeSkinChanges()
    }

    // ── State Transitions ──
    func transition(to newState: LivingState) {
        guard !humanControlPaused else { return }
        guard LivingEngine.isValidTransition(from: state, to: newState) else { return }
        let profile = skinEngine.profile(for: currentSkin)
        withAnimation(.easeInOut(duration: profile.dynamics.transitionSpeed)) { state = newState }
        onStateEnter(newState)
        stateMapper.recompute()
        liquidCore.transition(to: stateMapper.liquidTarget)
    }

    static func isValidTransition(from: LivingState, to: LivingState) -> Bool {
        let allowed: [LivingState: Set<LivingState>] = [
            .silent: [.thinking, .planning, .awaitingApproval, .recovery],
            .thinking: [.executing, .planning, .awaitingApproval, .silent],
            .planning: [.executing, .thinking, .awaitingApproval, .silent],
            .executing: [.learning, .silent, .recovery],
            .learning: [.silent, .executing, .recovery],
            .awaitingApproval: [.executing, .silent, .recovery],
            .recovery: [.silent, .thinking, .executing],
        ]
        return allowed[from]?.contains(to) ?? false
    }

    private func onStateEnter(_ newState: LivingState) {
        switch newState {
        case .learning:
            recentLearnings.append("新记忆节点已建立")
            if recentLearnings.count > 5 { recentLearnings.removeFirst() }
        case .awaitingApproval: pendingApprovalCount += 1
        case .recovery:
            recentLearnings.append("系统恢复中")
            if recentLearnings.count > 5 { recentLearnings.removeFirst() }
        default: break
        }
    }

    // ── Human Control Plane ──
    func pause()   { humanControlPaused = true }
    func resume()  { humanControlPaused = false }
    func approve() {
        if state == .awaitingApproval {
            pendingApprovalCount = max(0, pendingApprovalCount - 1)
            transition(to: .executing)
        }
    }
    func reject() {
        if state == .awaitingApproval {
            pendingApprovalCount = max(0, pendingApprovalCount - 1)
            transition(to: .silent)
        }
    }
    func modifyGoal(_ newGoal: String) {
        currentGoal = newGoal
        currentTask = newGoal
    }
    func setTask(_ task: String?) {
        currentTask = task
        if task != nil && (state == .silent || state == .recovery) { transition(to: .thinking) }
    }

    // ── Skin ──
    func switchSkin(to skin: LifeSkin) { skinEngine.switchSkin(to: skin) }
    private func observeSkinChanges() {
        skinEngine.$activeSkin.sink { [weak self] _ in self?.objectWillChange.send() }.store(in: &cancellables)
    }

    // ── Breath Cycle ──
    func breathCurve(at phase: Double) -> Double { sin(phase * 2 * .pi) }
    func gravityWellAttractor(x: Double, y: Double, centerX: Double, centerY: Double) -> Double {
        let dx = x - centerX; let dy = y - centerY
        let dist = max(sqrt(dx*dx + dy*dy), 0.1)
        return 1.0 / (dist * dist + 0.5)
    }

    private func startBreathCycle() {
        timer?.invalidate()
        timer = Timer.scheduledTimer(withTimeInterval: 0.05, repeats: true) { [weak self] _ in
            Task { @MainActor in
                guard let self, !self.isReducedMotion else { return }
                let period = self.skinProfile.dynamics.breathPeriod
                let elapsed = Date().timeIntervalSince1970.truncatingRemainder(dividingBy: period)
                let phase = elapsed / period
                self.breathPhase = sin(phase * 2 * .pi)
                // spatialBrain tick — only update orbit angles, NOT layout animation
                self.spatialBrain.tick()
            }
        }
    }

    // ── Accessibility ──
    private func observeReduceMotion() {
        #if os(macOS)
        isReducedMotion = NSWorkspace.shared.accessibilityDisplayShouldReduceMotion
        NotificationCenter.default.publisher(for: NSWorkspace.accessibilityDisplayOptionsDidChangeNotification)
            .sink { [weak self] _ in self?.isReducedMotion = NSWorkspace.shared.accessibilityDisplayShouldReduceMotion }
            .store(in: &cancellables)
        #elseif os(iOS)
        isReducedMotion = UIAccessibility.isReduceMotionEnabled
        NotificationCenter.default.publisher(for: UIAccessibility.reduceMotionStatusDidChangeNotification)
            .sink { [weak self] _ in self?.isReducedMotion = UIAccessibility.isReduceMotionEnabled }
            .store(in: &cancellables)
        #endif
    }

    // ── Microphone ──
    func toggleMicrophone() { microphoneEnabled.toggle() }

    deinit { timer?.invalidate() }
}
