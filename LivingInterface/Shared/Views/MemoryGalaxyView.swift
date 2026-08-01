import SwiftUI

// ── Memory Galaxy View V2: 记忆星系可视化 ──
// Orbiting memory nodes around the liquid core.
// Each node represents a memory category with its own
// orbit radius, speed, and visual weight.
// Nodes pulse when accessed, fade with distance in depth.

struct MemoryGalaxyView: View {
    @ObservedObject var engine: LivingEngine
    let center: CGPoint
    let coreRadius: CGFloat

    private var spatial: SpatialBrainEngine { engine.spatialBrain }
    private var theme: SpatialTheme { engine.skinEngine.spatialTheme() }

    var body: some View {
        ZStack {
            // ── Orbit ring guides ──
            orbitGuides

            // ── Memory nodes ──
            ForEach(spatial.memoryNodes) { node in
                memoryNodeView(node)
                    .position(node.position(center: center))
                    .opacity(node.opacity)
            }
        }
        .accessibilityLabel("记忆星系，\(spatial.memoryNodes.count) 个记忆区域")
    }

    // MARK: - Orbit Guides

    private var orbitGuides: some View {
        let baseRadius = spatial.memoryNodes.map(\.orbitRadius).reduce(0, +)
            / Double(max(1, spatial.memoryNodes.count))

        return Circle()
            .stroke(theme.galaxyAccent.opacity(theme.gridLineOpacity * 2), lineWidth: 0.5)
            .frame(width: baseRadius * 2, height: baseRadius * 2)
            .position(center)
    }

    // MARK: - Memory Node

    private func memoryNodeView(_ node: SpatialBrainEngine.MemoryNode) -> some View {
        ZStack {
            // Glow halo
            Circle()
                .fill(theme.nodeGlowColor)
                .frame(width: node.size * 1.8, height: node.size * 1.8)
                .blur(radius: node.size * 0.6)

            // Node body
            Circle()
                .fill(theme.galaxyAccent.opacity(0.8))
                .frame(width: node.size, height: node.size)
                .overlay(
                    Circle()
                        .stroke(theme.galaxyAccent.opacity(0.5), lineWidth: 1)
                )

            // Label
            Text(node.label)
                .font(.system(size: 9, weight: .medium))
                .foregroundColor(engine.skinProfile.colors.textSecondary)
                .offset(y: node.size / 2 + 10)
                .opacity(engine.isReducedMotion ? 0.3 : node.opacity * 0.7)
        }
        .scaleEffect(engine.isReducedMotion ? 1.0 : 0.95 + abs(engine.breathPhase) * 0.08)
        .animation(engine.isReducedMotion ? .none : .easeInOut(duration: 3.0), value: engine.breathPhase)
    }
}
