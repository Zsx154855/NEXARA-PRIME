import SwiftUI

// ── Liquid Core View V2: 液态生命核心可视化 ──
// Renders the organic liquid core with:
// - Deformable organic boundary via harmonic vertices
// - Internal particle system with fluid dynamics
// - Simulated light refraction and subsurface scattering
// - State-driven breath rhythm and thermal transitions
// - Glass-morphic membrane with fresnel highlights

struct LiquidCoreView: View {
    @ObservedObject var engine: LivingEngine
    let size: CGFloat

    private var liquidEngine: LiquidCoreEngine { engine.liquidCore }
    private var profile: SkinProfile { engine.skinProfile }
    private var stateMapping: StateSkinMapping {
        engine.skinEngine.stateMapping(for: engine.state)
    }
    private var spatialTheme: SpatialTheme {
        engine.skinEngine.spatialTheme()
    }

    var body: some View {
        ZStack {
            // ── Ambient nebula glow ──
            ambientGlowLayer

            // ── Organic liquid core ──
            liquidBodyLayer

            // ── Internal particle field ──
            if !engine.isReducedMotion {
                liquidParticleLayer
            }

            // ── Membrane boundary ──
            membraneLayer

            // ── Fresnel highlight ──
            fresnelHighlightLayer
        }
        .frame(width: size * 1.4, height: size * 1.4)
        .accessibilityLabel("NEXARA 液态生命核心，当前状态：\(engine.state.label)")
    }

    // MARK: - Ambient Glow

    private var ambientGlowLayer: some View {
        let glowIntensity = engine.isReducedMotion
            ? profile.lighting.glowOpacity * 0.5
            : profile.lighting.glowOpacity + abs(engine.breathPhase) * stateMapping.glowIntensity * 0.06

        return ZStack {
            // Outer soft glow
            Circle()
                .fill(profile.colors.deepGlow.opacity(glowIntensity))
                .frame(width: size * 1.3, height: size * 1.3)
                .blur(radius: profile.lighting.glowRadius)

            // Inner warm core
            Circle()
                .fill(stateMapping.coreColor.opacity(glowIntensity * 0.5))
                .frame(width: size * 0.6, height: size * 0.6)
                .blur(radius: profile.lighting.glowRadius * 0.4)
        }
        .animation(engine.isReducedMotion ? .none : .easeInOut(duration: profile.dynamics.breathPeriod),
                   value: engine.breathPhase)
    }

    // MARK: - Liquid Body

    private var liquidBodyLayer: some View {
        let deformation = engine.isReducedMotion ? 0 : liquidEngine.liquidState.deformation
        let viscosity = liquidEngine.liquidState.fluidViscosity

        return Canvas { context, canvasSize in
            let center = CGPoint(x: canvasSize.width / 2, y: canvasSize.height / 2)
            let radius = size / 2

            // Draw organic shape using boundary vertices
            let vertices = liquidEngine.boundaryVertices(center: center, radius: radius)
            guard vertices.count >= 3 else { return }

            var path = Path()
            path.move(to: vertices[0])

            for i in 0..<vertices.count {
                let current = vertices[i]
                let next = vertices[(i + 1) % vertices.count]
                let cp1x = current.x + (next.x - current.x) * 0.4
                let cp1y = current.y + (next.y - current.y) * 0.4 + CGFloat(deformation * viscosity * 15)
                path.addCurve(to: next, control1: CGPoint(x: cp1x, y: cp1y),
                              control2: CGPoint(x: (current.x + next.x) / 2, y: (current.y + next.y) / 2))
            }
            path.closeSubpath()

            // Fill with glass gradient
            let glassGradient = Gradient(colors: [
                stateMapping.coreColor.opacity(liquidEngine.liquidState.coreOpacity),
                stateMapping.coreColor.opacity(liquidEngine.liquidState.coreOpacity * 0.7),
            ])
            context.fill(path, with: .linearGradient(
                glassGradient,
                startPoint: CGPoint(x: center.x - radius * 0.3, y: center.y - radius * 0.3),
                endPoint: CGPoint(x: center.x + radius * 0.3, y: center.y + radius * 0.3)
            ))

            // Subsurface scattering inner glow
            let innerGlow = Path(ellipseIn: CGRect(
                x: center.x - radius * 0.25,
                y: center.y - radius * 0.25,
                width: radius * 0.5,
                height: radius * 0.5
            ))
            context.fill(innerGlow, with: .color(profile.colors.deepGlow.opacity(
                profile.lighting.subsurfaceIntensity * liquidEngine.liquidState.coreOpacity
            )))
        }
        .animation(engine.isReducedMotion ? .none : .easeInOut(duration: profile.dynamics.breathPeriod),
                   value: engine.breathPhase)
    }

    // MARK: - Liquid Particles

    private var liquidParticleLayer: some View {
        Canvas { context, canvasSize in
            let center = CGPoint(x: canvasSize.width / 2, y: canvasSize.height / 2)
            let radius = size / 2
            let now = Date().timeIntervalSince1970

            for p in liquidEngine.particleStates.prefix(liquidEngine.liquidState.internalParticleCount) {
                let x = center.x + CGFloat(cos(p.angle) * p.radius * radius)
                let y = center.y + CGFloat(sin(p.angle) * p.radius * radius)

                // Refraction offset
                let point = CGPoint(x: x, y: y)
                let refract = VisualPhysicsEngine.refractionDisplacement(
                    point: point, center: center,
                    refractiveIndex: liquidEngine.liquidState.refractionIndex,
                    surfaceCurvature: liquidEngine.liquidState.deformation,
                    time: now
                )
                let rx = x + refract.width
                let ry = y + refract.height

                let particleSize = p.size * (0.8 + abs(sin(p.phase + now * 0.5)) * 0.4)
                let particleOpacity = p.opacity * liquidEngine.liquidState.coreOpacity

                let rect = CGRect(
                    x: rx - particleSize / 2, y: ry - particleSize / 2,
                    width: particleSize, height: particleSize
                )

                // Inner bright core
                let innerRect = CGRect(
                    x: rx - particleSize / 4, y: ry - particleSize / 4,
                    width: particleSize / 2, height: particleSize / 2
                )

                context.fill(Path(ellipseIn: rect),
                             with: .color(profile.colors.particleInner.opacity(particleOpacity)))
                context.fill(Path(ellipseIn: innerRect),
                             with: .color(.white.opacity(particleOpacity * 0.5)))
            }
        }
    }

    // MARK: - Membrane

    private var membraneLayer: some View {
        let deformation = engine.isReducedMotion ? 0 : liquidEngine.liquidState.deformation

        return Canvas { context, canvasSize in
            let center = CGPoint(x: canvasSize.width / 2, y: canvasSize.height / 2)
            let radius = size / 2

            let membranePath = Path(liquidEngine.membranePath(center: center, radius: radius))
            context.stroke(
                membranePath,
                with: .linearGradient(
                    Gradient(colors: [
                        profile.colors.membraneHighlight.opacity(0.5 * (1.0 - deformation * 0.3)),
                        profile.colors.membraneHighlight.opacity(0.15),
                        profile.colors.membraneHighlight.opacity(0.4 * (1.0 - deformation * 0.2)),
                    ]),
                    startPoint: CGPoint(x: center.x - radius, y: center.y - radius),
                    endPoint: CGPoint(x: center.x + radius, y: center.y + radius)
                ),
                style: StrokeStyle(lineWidth: 1.5 + deformation * 0.8, lineCap: .round)
            )
        }
    }

    // MARK: - Fresnel Highlight

    private var fresnelHighlightLayer: some View {
        let strength = profile.lighting.fresnelStrength

        return Circle()
            .trim(from: 0.55, to: 0.72)
            .stroke(
                AngularGradient(
                    gradient: Gradient(colors: [
                        .white.opacity(0),
                        .white.opacity(strength * 0.6),
                        .white.opacity(strength * 0.8),
                        .white.opacity(strength * 0.3),
                        .white.opacity(0),
                    ]),
                    center: .center,
                    startAngle: .degrees(160),
                    endAngle: .degrees(290)
                ),
                style: StrokeStyle(lineWidth: 3, lineCap: .round)
            )
            .frame(width: size * 0.9, height: size * 0.9)
            .blur(radius: 4)
            .opacity(engine.isReducedMotion ? 0.3 : 0.6 + abs(engine.breathPhase) * 0.15)
            .animation(engine.isReducedMotion ? .none : .easeInOut(duration: profile.dynamics.breathPeriod),
                       value: engine.breathPhase)
    }
}
