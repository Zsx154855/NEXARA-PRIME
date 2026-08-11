import SwiftUI

/// State indicator capsule with breath animation on dot.
struct StateIndicator: View {
    @ObservedObject var engine: LivingEngine

    var body: some View {
        HStack(spacing: 8) {
            Circle()
                .fill(engine.state.color)
                .frame(width: 10, height: 10)
                .scaleEffect(engine.isReducedMotion ? 1.0 : 1.0 + abs(engine.breathPhase) * 0.3)
                .animation(
                    engine.isReducedMotion ? .none : .easeInOut(duration: engine.skinProfile.dynamics.breathPeriod / 2),
                    value: engine.breathPhase
                )

            Text(engine.state.rawValue)
                .font(.system(size: 13, weight: .medium))
                .foregroundColor(engine.skinProfile.colors.textPrimary)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 7)
        .background(Capsule().fill(.ultraThinMaterial))
        .overlay(Capsule().stroke(engine.state.color.opacity(0.4), lineWidth: 0.5))
    }
}
