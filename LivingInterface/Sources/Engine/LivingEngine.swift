import SwiftUI
import Combine

/// Central engine driving living interface state, skin, and breath cycles.
@MainActor
final class LivingEngine: ObservableObject {
    @Published var state: LivingState = .silent
    @Published var skin: LifeSkin = .morningMist
    @Published var breathPhase: Double = 0.0
    @Published var isReducedMotion: Bool = false
    @Published var microphoneEnabled: Bool = false  // default OFF per privacy spec
    
    private var timer: Timer?
    private let breathFrequencyRange: ClosedRange<Double> = 0.2...1.5
    
    init() {
        startBreathCycle()
        observeReduceMotion()
    }
    
    func transition(to newState: LivingState) {
        guard LivingEngine.isValidTransition(from: state, to: newState) else { return }
        withAnimation(.easeInOut(duration: 0.8)) {
            state = newState
        }
    }
    
    func switchSkin(to newSkin: LifeSkin) {
        withAnimation(.easeInOut(duration: 1.2)) {
            skin = newSkin
        }
    }
    
    static func isValidTransition(from: LivingState, to: LivingState) -> Bool {
        let allowed: [LivingState: Set<LivingState>] = [
            .silent: [.thinking],
            .thinking: [.executing, .awaitingApproval],
            .executing: [.learning, .silent],
            .learning: [.silent],
            .awaitingApproval: [.executing, .silent],
        ]
        return allowed[from]?.contains(to) ?? false
    }
    
    // ── Breath Cycle ──
    private func startBreathCycle() {
        timer?.invalidate()
        timer = Timer.scheduledTimer(withTimeInterval: 0.05, repeats: true) { [weak self] _ in
            Task { @MainActor in
                guard let self, !self.isReducedMotion else { return }
                let period = self.skin.breathPeriod
                let elapsed = Date().timeIntervalSince1970.truncatingRemainder(dividingBy: period)
                self.breathPhase = sin(elapsed / period * 2 * .pi)
            }
        }
    }
    
    private func observeReduceMotion() {
        #if os(iOS) || os(macOS)
        isReducedMotion = AccessibilitySettings.isReduceMotionEnabled
        #endif
    }
    
    deinit { timer?.invalidate() }
}

// ── Stub for accessibility check ──
enum AccessibilitySettings {
    static var isReduceMotionEnabled: Bool {
        #if os(macOS)
        return NSWorkspace.shared.accessibilityDisplayShouldReduceMotion
        #else
        return false
        #endif
    }
}
