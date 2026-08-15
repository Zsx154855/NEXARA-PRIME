import SwiftUI

// MARK: - Living Core V3: NEXARA 主脑核心可视化
// Central living brain — the primary visual anchor.
// Multi-layer: core pulse, dual neural orbits, state halo, activity response.
// Targets ~48%-62% of content width on iPhone 15 Pro Max.

struct LivingCore: View {
    @ObservedObject var engine: LivingEngine
    let containerWidth: CGFloat

    private var coreSize: CGFloat {
        containerWidth * 0.60  // ~60% of content width — primary visual anchor
    }

    private var stateMapping: StateSkinMapping {
        engine.skinEngine.stateMapping(for: engine.state)
    }

    private var profile: SkinProfile {
        engine.skinProfile
    }

    var body: some View {
        ZStack {
            // Layer 1: State halo
            stateHaloLayer

            // Layer 2: Neural orbit — slow, outer
            if !engine.isReducedMotion {
                neuralOrbitLayer(speed: 1.0, count: 4, radius: 0.52, opacity: 0.12, clockwise: true)
            }

            // Layer 3: Neural orbit — faster, inner
            if !engine.isReducedMotion {
                neuralOrbitLayer(speed: 1.6, count: 3, radius: 0.38, opacity: 0.16, clockwise: false)
            }

            // Layer 4: Core body
            coreBodyLayer

            // Layer 5: Core pulse ring
            corePulseRing

            // Layer 6: Center nucleus
            centerNucleus
        }
        .frame(width: coreSize * 1.35, height: coreSize * 1.35)
        .drawingGroup()  // GPU rasterize — single texture for all 6 layers
        .rotation3DEffect(  // subtle 3D tilt for genuine depth perception
            .degrees(engine.isReducedMotion ? 0 : 3 + engine.breathPhase * 2),
            axis: (x: 0.3, y: 0.7, z: 0),
            perspective: 0.3
        )
        .accessibilityLabel("NEXARA 主脑，当前状态：\(engine.state.label)")
        .accessibilityIdentifier("living.brain")
    }

    // MARK: - State Halo

    private var stateHaloLayer: some View {
        let coreColor = stateMapping.coreColor
        let glowIntensity = engine.isReducedMotion
            ? profile.lighting.glowOpacity * 0.4
            : profile.lighting.glowOpacity + abs(engine.breathPhase) * 0.03
        let breathPeriod = NXMotion.breathPeriod(for: engine.currentSkin)
        return Circle()
            .fill(
                RadialGradient(
                    gradient: Gradient(colors: [
                        coreColor.opacity(glowIntensity * 1.2),
                        coreColor.opacity(glowIntensity * 0.5),
                        coreColor.opacity(0),
                    ]),
                    center: .center,
                    startRadius: coreSize * 0.2,
                    endRadius: coreSize * 0.7
                )
            )
            .frame(width: coreSize * 1.3, height: coreSize * 1.3)
            .blur(radius: engine.isReducedMotion ? 8 : 4)
            .animation(engine.isReducedMotion ? .none : .easeInOut(duration: breathPeriod),
                       value: engine.breathPhase)
    }

    // MARK: - Neural Orbit Layer

    private func neuralOrbitLayer(speed: Double, count: Int, radius: Double, opacity: Double, clockwise: Bool) -> some View {
        let r = coreSize * radius
        let orbitColor = stateMapping.coreColor

        return ZStack {
            // Orbit ring
            Circle()
                .stroke(orbitColor.opacity(opacity * 0.5), lineWidth: 0.5)
                .frame(width: r * 2, height: r * 2)

            // Nodes on orbit
            ForEach(0..<count, id: \.self) { i in
                let baseAngle = Double(i) * (2 * .pi / Double(count))
                let phase = engine.breathPhase
                let direction = clockwise ? 1.0 : -1.0
                let angle = baseAngle + phase * 0.4 * speed * direction

                Circle()
                    .fill(orbitColor.opacity(opacity * 2.0))
                    .frame(width: 6, height: 6)
                    .offset(x: cos(angle) * r, y: sin(angle) * r)
            }
        }
        .animation(engine.isReducedMotion ? .none : .linear(duration: NXMotion.orbitDurationSlow / speed),
                   value: engine.breathPhase)
    }

    // MARK: - Core Body

    private var coreBodyLayer: some View {
        let coreColor = stateMapping.coreColor
        let breathPeriod = NXMotion.breathPeriod(for: engine.currentSkin)
        return ZStack {
            Circle()
                .fill(
                    RadialGradient(
                        gradient: Gradient(colors: [
                            coreColor.opacity(0.35),
                            coreColor.opacity(0.18),
                            coreColor.opacity(0.06),
                        ]),
                        center: .topLeading,
                        startRadius: 0,
                        endRadius: coreSize * 0.5
                    )
                )
                .frame(width: coreSize * 0.62, height: coreSize * 0.62)
                .overlay(
                    Circle()
                        .stroke(coreColor.opacity(0.25), lineWidth: 0.5)
                        .frame(width: coreSize * 0.62, height: coreSize * 0.62)
                )
            Circle()
                .fill(
                    RadialGradient(
                        gradient: Gradient(colors: [
                            Color.white.opacity(0.25),
                            Color.white.opacity(0.05),
                            Color.clear,
                        ]),
                        center: .topLeading,
                        startRadius: 0,
                        endRadius: coreSize * 0.3
                    )
                )
                .frame(width: coreSize * 0.55, height: coreSize * 0.55)
                .scaleEffect(engine.isReducedMotion ? 1.0 : 0.97 + abs(engine.breathPhase) * 0.03)
        }
        .animation(engine.isReducedMotion ? .none : .easeInOut(duration: breathPeriod),
                   value: engine.breathPhase)
    }

    // MARK: - Core Pulse Ring

    private var corePulseRing: some View {
        Circle()
            .stroke(stateMapping.coreColor.opacity(0.2), lineWidth: 1)
            .frame(width: coreSize * 0.58, height: coreSize * 0.58)
            .scaleEffect(engine.isReducedMotion ? 1.0 : 0.95 + abs(engine.breathPhase) * 0.08)
            .animation(engine.isReducedMotion ? .none : .easeInOut(duration: NXMotion.pulseDuration),
                       value: engine.breathPhase)
    }

    // MARK: - Center Nucleus

    private var centerNucleus: some View {
        let nucleusColor = stateMapping.coreColor
        let pulseDur = NXMotion.pulseDuration
        return ZStack {
            Circle()
                .fill(nucleusColor.opacity(0.5))
                .frame(width: coreSize * 0.1, height: coreSize * 0.1)
            Circle()
                .fill(Color.white.opacity(0.4))
                .frame(width: coreSize * 0.04, height: coreSize * 0.04)
                .offset(x: coreSize * 0.01, y: -coreSize * 0.01)
        }
        .scaleEffect(engine.isReducedMotion ? 1.0 : 0.95 + abs(engine.breathPhase) * 0.06)
        .animation(engine.isReducedMotion ? .none : .easeInOut(duration: pulseDur * 0.7),
                   value: engine.breathPhase)
    }
}

// MARK: - Particle Field (unchanged from V2)

struct ParticleField: View {
    let config: ParticleConfig
    let multiplier: Double
    let breathPhase: Double
    let size: CGFloat

    private var effectiveCount: Int { Int(Double(config.count) * multiplier) }

    var body: some View {
        Canvas { context, canvasSize in
            let center = CGPoint(x: canvasSize.width / 2, y: canvasSize.height / 2)

            for i in 0..<effectiveCount {
                let seed = Double(i) * 0.618033988749895
                let radius: Double

                switch config.behavior {
                case .float:
                    radius = size * 0.3 + sin(seed * 10 + breathPhase * 2) * size * 0.15
                case .rise:
                    radius = size * 0.25 + cos(seed * 8 + breathPhase * 1.5) * size * 0.2
                case .orbit:
                    radius = size * 0.35
                case .pulse:
                    radius = size * 0.2 + abs(sin(seed * 6 + breathPhase * 3)) * size * 0.2
                }

                let angle: Double
                switch config.behavior {
                case .orbit:
                    angle = seed * .pi * 2 + breathPhase * 0.5
                case .float:
                    angle = seed * .pi * 2 + breathPhase * 0.3
                default:
                    angle = seed * .pi * 2
                }

                let x = center.x + cos(angle) * radius
                let y = center.y + sin(angle) * radius
                let particleSize = config.size.lowerBound + (config.size.upperBound - config.size.lowerBound) * abs(sin(seed * 13))
                let opacity = config.opacity.lowerBound + (config.opacity.upperBound - config.opacity.lowerBound) * abs(cos(seed * 7 + breathPhase))

                let rect = CGRect(x: x - particleSize / 2, y: y - particleSize / 2,
                                  width: particleSize, height: particleSize)
                context.fill(
                    Path(ellipseIn: rect),
                    with: .color(config.color.opacity(opacity))
                )
            }
        }
    }
}
