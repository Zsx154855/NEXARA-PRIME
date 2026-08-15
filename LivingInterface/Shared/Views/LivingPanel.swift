import SwiftUI

/// Glass-morphic living panel with liquid breath animation.
struct LivingPanel<Content: View>: View {
    @ObservedObject var engine: LivingEngine
    @ViewBuilder let content: () -> Content

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 24)
                .fill(engine.skinProfile.colors.primary.opacity(
                    engine.isReducedMotion ? 0.08 : 0.06 + abs(engine.breathPhase) * 0.04))
                .background(
                    RoundedRectangle(cornerRadius: 24)
                        .fill(.ultraThinMaterial)
                        .environment(\.colorScheme, .light)
                )
                .overlay(
                    RoundedRectangle(cornerRadius: 24)
                        .stroke(engine.skinProfile.colors.secondary.opacity(0.3), lineWidth: 0.5)
                )

            content()
                .padding(24)
        }
        .clipShape(RoundedRectangle(cornerRadius: 24))
        .shadow(color: engine.skinProfile.colors.shadow, radius: 20, x: 0, y: 4)
    }
}

// MARK: - NEXARA Glass Material System V3
// Unified glass components using system materials with consistent depth treatment.

enum GlassLevel {
    case subtle, standard, elevated, prominent
    var material: Material {
        switch self {
        case .subtle: .ultraThinMaterial
        case .standard: .thinMaterial
        case .elevated: .regularMaterial
        case .prominent: .thickMaterial
        }
    }
    var highlightOpacity: Double {
        switch self {
        case .subtle: 0.15; case .standard: 0.25
        case .elevated: 0.35; case .prominent: 0.4
        }
    }
}

struct GlassSurface<Content: View>: View {
    let level: GlassLevel; let cornerRadius: CGFloat
    @ViewBuilder let content: () -> Content
    var body: some View {
        content()
            .background(
                RoundedRectangle(cornerRadius: cornerRadius)
                    .fill(level.material).environment(\.colorScheme, .light)
            )
            .overlay(RoundedRectangle(cornerRadius: cornerRadius).stroke(NXColor.glassBorder, lineWidth: 0.5))
            .overlay(
                RoundedRectangle(cornerRadius: cornerRadius)
                    .stroke(NXColor.glassHighlight.opacity(level.highlightOpacity), lineWidth: 0.5).padding(1)
            )
            .shadow(color: NXColor.glassShadow, radius: 12, x: 0, y: 2)
            .clipShape(RoundedRectangle(cornerRadius: cornerRadius))
    }
}

struct GlassComposer: View {
    @Binding var text: String
    let placeholder: String; let accentColor: Color
    let onSubmit: () -> Void
    @FocusState.Binding var isFocused: Bool
    var body: some View {
        HStack(alignment: .bottom, spacing: NXSpacing.sm) {
            TextField(placeholder, text: $text, axis: .vertical)
                .focused($isFocused).font(NXTypography.bodyFont)
                .foregroundColor(NXColor.graphite)
                .padding(.horizontal, NXSpacing.lg).padding(.vertical, NXSpacing.md)
                .lineLimit(1...5).accessibilityLabel("指令输入框")
            Button {
                onSubmit()
            } label: {
                Image(systemName: NXIcon.send).font(.system(size: 28))
                    .foregroundColor(text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? NXColor.graphiteSecondary.opacity(0.3) : accentColor)
                    .symbolRenderingMode(.hierarchical)
            }
            .buttonStyle(.plain)
            .disabled(text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            .frame(width: NXHitTarget.minimum, height: NXHitTarget.minimum)
            .accessibilityLabel("发送指令").padding(.trailing, NXSpacing.sm).padding(.bottom, NXSpacing.xs)
        }
        .background(RoundedRectangle(cornerRadius: NXRadius.composer).fill(.regularMaterial).environment(\.colorScheme, .light))
        .overlay(RoundedRectangle(cornerRadius: NXRadius.composer).stroke(NXColor.glassBorder, lineWidth: 0.5))
        .overlay(RoundedRectangle(cornerRadius: NXRadius.composer).stroke(NXColor.glassHighlight.opacity(0.3), lineWidth: 0.5).padding(1))
        .shadow(color: Color.black.opacity(0.06), radius: 16, x: 0, y: 4)
        .clipShape(RoundedRectangle(cornerRadius: NXRadius.composer))
        .padding(.horizontal, NXSpacing.pageHorizontal)
    }
}

struct GlassTabBar: View {
    @Binding var selectedTab: Int
    let tabs: [(title: String, icon: String)]
    let accentColor: Color; let textSecondary: Color
    var body: some View {
        HStack(spacing: 0) {
            ForEach(Array(tabs.enumerated()), id: \.offset) { index, tab in
                Button {
                    withAnimation(.easeInOut(duration: NXMotion.transitionDefault)) { selectedTab = index }
                } label: {
                    VStack(spacing: NXSpacing.xs) {
                        Image(systemName: tab.icon).font(.system(size: 18, weight: .regular))
                            .symbolRenderingMode(.hierarchical).frame(height: 22)
                        Text(tab.title).font(NXTypography.captionFont)
                    }
                    .foregroundColor(selectedTab == index ? accentColor : textSecondary.opacity(0.5))
                    .frame(maxWidth: .infinity).frame(height: NXHitTarget.minimum + 8)
                }
                .buttonStyle(.plain)
                .accessibilityLabel("\(tab.title)标签")
                .accessibilityAddTraits(selectedTab == index ? .isSelected : [])
            }
        }
        .padding(.horizontal, NXSpacing.md).padding(.vertical, NXSpacing.sm)
        .background(RoundedRectangle(cornerRadius: NXRadius.tabBar).fill(.thickMaterial).environment(\.colorScheme, .light))
        .overlay(RoundedRectangle(cornerRadius: NXRadius.tabBar).stroke(NXColor.glassBorder, lineWidth: 0.5))
        .shadow(color: Color.black.opacity(0.05), radius: 12, x: 0, y: -2)
        .clipShape(RoundedRectangle(cornerRadius: NXRadius.tabBar))
        .padding(.horizontal, NXSpacing.pageHorizontal)
    }
}

struct GlassChip: View {
    let text: String; let color: Color; let isSelected: Bool; let action: () -> Void
    var body: some View {
        Button(action: action) {
            Text(text).font(NXTypography.labelFont)
                .foregroundColor(isSelected ? NXColor.graphite : NXColor.graphiteSecondary)
                .padding(.horizontal, NXSpacing.md).padding(.vertical, NXSpacing.sm)
                .background(Capsule().fill(isSelected ? color.opacity(0.15) : .clear))
                .overlay(Capsule().stroke(isSelected ? color.opacity(0.35) : NXColor.graphiteSecondary.opacity(0.15), lineWidth: 0.5))
        }.buttonStyle(.plain)
    }
}

struct GlassButton: View {
    let label: String; let icon: String; let color: Color; let action: () -> Void
    var body: some View {
        Button(action: action) {
            HStack(spacing: NXSpacing.xs) {
                Image(systemName: icon).font(.system(size: 13))
                Text(label).font(NXTypography.secondaryFont.weight(.medium))
            }
            .foregroundColor(color).padding(.horizontal, NXSpacing.md).padding(.vertical, NXSpacing.sm)
            .background(Capsule().fill(color.opacity(0.12)))
            .overlay(Capsule().stroke(color.opacity(0.3), lineWidth: 0.5))
        }.buttonStyle(.plain)
    }
}

// MARK: - Ambient Particle View

struct AmbientParticleView: View {
    @ObservedObject var engine: LivingEngine

    private let particleCount: Int = 20  // reduced from 30 — fewer particles, smoother frame rate
    @State private var particles: [AmbientParticleData] = []

    var body: some View {
        TimelineView(.animation(minimumInterval: 0.067)) { timeline in  // ~15fps instead of ~20fps
            Canvas { context, size in
                let now = timeline.date.timeIntervalSince1970
                let center = CGPoint(x: size.width / 2, y: size.height / 2)
                let profile = engine.skinProfile
                let baseColor = profile.colors.primary
                let accentColor = profile.colors.accent
                let bpmFactor = engine.audioResonance.currentBPM > 0
                    ? min(2.0, engine.audioResonance.currentBPM / 60.0) : 1.0
                let beatBoost = engine.audioResonance.latestSnapshot.isBeat ? 1.5 : 1.0

                for p in particles {
                    let drift = VisualPhysicsEngine.noiseFieldFast(
                        at: p.position, time: now * p.speed, scale: 0.003, strength: 0.5)
                    let gravity = VisualPhysicsEngine.gravityWell(
                        position: p.position, center: center, mass: 0.3, deltaTime: 0.067)
                    let pos = CGPoint(
                        x: p.position.x + drift.x * 0.3 + (gravity.x - p.position.x) * 0.002,
                        y: p.position.y + drift.y * 0.3 + (gravity.y - p.position.y) * 0.002)
                    let wrappedX = ((pos.x.truncatingRemainder(dividingBy: size.width)) + size.width)
                        .truncatingRemainder(dividingBy: size.width)
                    let wrappedY = ((pos.y.truncatingRemainder(dividingBy: size.height)) + size.height)
                        .truncatingRemainder(dividingBy: size.height)
                    let pulseSize = p.size * (0.8 + abs(sin(now * p.frequency + p.phase)) * 0.4)
                        * bpmFactor * beatBoost
                    context.fill(
                        Path(ellipseIn: CGRect(x: wrappedX - pulseSize * 2, y: wrappedY - pulseSize * 2,
                                               width: pulseSize * 4, height: pulseSize * 4)),
                        with: .color(accentColor.opacity(p.opacity * 0.08)))
                    context.fill(
                        Path(ellipseIn: CGRect(x: wrappedX - pulseSize / 2, y: wrappedY - pulseSize / 2,
                                               width: pulseSize, height: pulseSize)),
                        with: .color(baseColor.opacity(p.opacity * 0.4)))
                    context.fill(
                        Path(ellipseIn: CGRect(x: wrappedX - pulseSize / 4, y: wrappedY - pulseSize / 4,
                                               width: pulseSize / 2, height: pulseSize / 2)),
                        with: .color(.white.opacity(p.opacity * 0.3)))
                }
            }
        }
        .drawingGroup()  // GPU rasterize — single texture for particle field
        .opacity(engine.isReducedMotion ? 0 : 0.6)
        .onAppear { initializeParticles() }
    }

    private func initializeParticles() {
        particles = (0..<particleCount).map { i in
            let seed = Double(i) * 0.618033988749895
            return AmbientParticleData(
                id: i,
                position: CGPoint(x: Double.random(in: 0...1200), y: Double.random(in: 0...800)),
                size: Double.random(in: 1.5...4.0),
                opacity: Double.random(in: 0.15...0.45),
                speed: 0.3 + seed * 0.7, frequency: 0.5 + seed * 1.5, phase: seed * .pi * 2)
        }
    }
}

private struct AmbientParticleData {
    let id: Int; var position: CGPoint; let size: Double
    let opacity: Double; let speed: Double; let frequency: Double; let phase: Double
}
