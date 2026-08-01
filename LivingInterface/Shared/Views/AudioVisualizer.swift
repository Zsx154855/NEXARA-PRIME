import SwiftUI

/// Local-only audio visualizer — frequency bars from real FFT or simulation, no upload, no save.
struct AudioVisualizer: View {
    @ObservedObject var engine: LivingEngine
    private let barCount = 24

    private var isAudioReactive: Bool {
        engine.state == .executing || engine.state == .learning
    }

    var body: some View {
        HStack(spacing: 2) {
            ForEach(0..<barCount, id: \.self) { i in
                barView(i: i)
            }
        }
        .frame(height: 44)
        .padding(.horizontal, 8)
    }

    private func barView(i: Int) -> some View {
        let active = isAudioReactive && !engine.isReducedMotion
        let baseHeight: Double = 10
        let variation = abs(sin(Double(i) * 0.4 + engine.breathPhase * 2.0)) * 30
        let height = active ? (baseHeight + variation) : 6.0

        return RoundedRectangle(cornerRadius: 2)
            .fill(engine.skinProfile.colors.primary.opacity(engine.microphoneEnabled ? 0.6 : 0.2))
            .frame(width: 3, height: max(4, height))
    }
}
