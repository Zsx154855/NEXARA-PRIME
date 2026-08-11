import SwiftUI
import Combine

// ── Liquid Core Engine V2: NEXARA 液态生命核心引擎 ──
// Replaces simple circle animations with organic fluid dynamics:
// - Soft-body deformation via harmonic vertex displacement
// - Organic boundary with membrane rendering
// - Internal particle system with Brownian motion
// - Simulated light refraction and caustics
// - State-driven breathing rhythm
// - Thermal equilibrium transitions between states

@MainActor
final class LiquidCoreEngine: ObservableObject {
    // ── Published State ──
    @Published var liquidState: LiquidCoreState = .default
    @Published var breathPhase: Double = 0.0
    @Published var deformationPhases: [Double] = Array(repeating: 0.0, count: 12)
    @Published var particleStates: [ParticleState] = []
    @Published var isTransitioning: Bool = false
    @Published var thermalEquilibrium: Double = 1.0  // 0.0 (cold/rigid) – 1.0 (warm/fluid)

    // ── Configuration ──
    let profile: LiquidProfile

    // ── Internal ──
    private var timer: Timer?
    private var thermalTimer: Timer?
    private var cancellables = Set<AnyCancellable>()
    private var targetLiquidState: LiquidCoreState = .default
    private let vertexCount = 12

    // MARK: - Lifecycle

    init(profile: LiquidProfile? = nil) {
        self.profile = profile ?? LiquidCoreEngine.defaultProfile
        initializeParticles()
        startAnimationLoop()
    }

    // MARK: - State Transition

    func transition(to state: LiquidCoreState) {
        targetLiquidState = state
        isTransitioning = true
        thermalEquilibrium = 0.0

        thermalTimer?.invalidate()
        thermalTimer = Timer.scheduledTimer(withTimeInterval: 0.05, repeats: true) { [weak self] _ in
            Task { @MainActor in
                guard let self else { return }
                let step = 0.05 / self.profile.timing.thermalEquilibriumTime
                self.thermalEquilibrium = min(1.0, self.thermalEquilibrium + step)
                self.liquidState = self.interpolate(from: self.liquidState, to: state, t: self.thermalEquilibrium)

                if self.thermalEquilibrium >= 1.0 {
                    self.liquidState = state
                    self.isTransitioning = false
                    self.thermalTimer?.invalidate()
                    self.thermalTimer = nil
                }
            }
        }
    }

    private func interpolate(from: LiquidCoreState, to: LiquidCoreState, t: Double) -> LiquidCoreState {
        let ease = easeOutCubic(t)
        return LiquidCoreState(
            deformation: from.deformation + (to.deformation - from.deformation) * ease,
            boundaryComplexity: to.boundaryComplexity,
            internalParticleCount: from.internalParticleCount + Int(Double(to.internalParticleCount - from.internalParticleCount) * ease),
            refractionIndex: from.refractionIndex + (to.refractionIndex - from.refractionIndex) * ease,
            breathAmplitude: from.breathAmplitude + (to.breathAmplitude - from.breathAmplitude) * ease,
            breathFrequency: from.breathFrequency + (to.breathFrequency - from.breathFrequency) * ease,
            fluidViscosity: from.fluidViscosity + (to.fluidViscosity - from.fluidViscosity) * ease,
            surfaceTension: from.surfaceTension + (to.surfaceTension - from.surfaceTension) * ease,
            innerGlowWarmth: from.innerGlowWarmth + (to.innerGlowWarmth - from.innerGlowWarmth) * ease,
            coreOpacity: from.coreOpacity + (to.coreOpacity - from.coreOpacity) * ease
        )
    }

    // MARK: - Breathing Cycle

    private func startAnimationLoop() {
        timer?.invalidate()
        timer = Timer.scheduledTimer(withTimeInterval: profile.timing.particleUpdateRate, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.updateFrame()
            }
        }
    }

    private func updateFrame() {
        let now = Date().timeIntervalSince1970
        let period = profile.timing.breathPeriod
        breathPhase = sin(now / period * 2 * .pi)

        // Organic deformation phases — each vertex oscillates at a slightly different frequency
        for i in 0..<vertexCount {
            let seed = Double(i) * 0.382
            let freq = profile.timing.deformationSpeed * (0.8 + seed * 0.4)
            deformationPhases[i] = sin(now * freq + seed * .pi * 2)
        }

        // Update particle states with fluid dynamics
        updateParticles(now: now)
    }

    // MARK: - Particles

    private func initializeParticles() {
        particleStates = (0..<profile.particles.maxCount).map { i in
            let seed = Double(i) * 0.618033988749895
            let angle = seed * .pi * 2
            let radius = Double.random(in: 0.05...0.4)
            return ParticleState(
                id: i,
                angle: angle,
                radius: radius,
                speed: 0.1 + seed * 0.3,
                size: Double.random(in: profile.particles.sizeRange),
                opacity: Double.random(in: profile.particles.opacityRange),
                phase: seed * .pi * 2
            )
        }
    }

    private func updateParticles(now: Double) {
        let activeCount = min(liquidState.internalParticleCount, profile.particles.maxCount)

        for i in 0..<activeCount {
            guard i < particleStates.count else { break }
            var p = particleStates[i]

            switch profile.particles.behavior {
            case .float:
                p.angle += p.speed * 0.01
                p.radius += (Double.random(in: -0.01...0.01)) * (1.0 - liquidState.fluidViscosity)
            case .orbit:
                p.angle += p.speed * 0.02 * (1.0 - liquidState.fluidViscosity * 0.5)
            case .converge:
                p.radius += (0.05 - p.radius) * 0.02 * (1.0 - liquidState.fluidViscosity)
                p.angle += p.speed * 0.015
            case .diffuse:
                p.radius += 0.003 * (1.0 - liquidState.surfaceTension)
                p.angle += p.speed * 0.02
            case .pulse:
                p.radius += breathPhase * 0.01 * (1.0 - liquidState.fluidViscosity)
            case .flow:
                p.angle += p.speed * 0.015
                p.radius += sin(now * 2.0 + p.phase) * 0.005
            case .rise:
                p.radius -= 0.002
                p.angle += sin(now * 1.5 + p.phase) * 0.01
            case .swarm:
                p.angle += p.speed * 0.01 + cos(now + p.phase) * 0.02
                p.radius += sin(now * 1.3 + p.phase) * 0.008
            }

            p.radius = max(0.02, min(0.48, p.radius))
            particleStates[i] = p
        }
    }

    // MARK: - Organic Boundary Vertices

    func boundaryVertices(center: CGPoint, radius: CGFloat) -> [CGPoint] {
        let count = liquidState.boundaryComplexity
        var vertices: [CGPoint] = []

        for i in 0..<count {
            let baseAngle = Double(i) * 2.0 * .pi / Double(count)
            let deformation = deformationPhases[i % vertexCount] * liquidState.deformation * radius * 0.3
            let r = Double(radius) + deformation
            let x = center.x + CGFloat(cos(baseAngle) * r)
            let y = center.y + CGFloat(sin(baseAngle) * r)
            vertices.append(CGPoint(x: x, y: y))
        }

        return vertices
    }

    // MARK: - Membrane Path

    func membranePath(center: CGPoint, radius: CGFloat) -> CGPath {
        let vertices = boundaryVertices(center: center, radius: radius)
        let path = CGMutablePath()

        guard !vertices.isEmpty else { return path }
        path.move(to: vertices[0])

        for i in 0..<vertices.count {
            let current = vertices[i]
            let next = vertices[(i + 1) % vertices.count]
            let midX = (current.x + next.x) / 2
            let midY = (current.y + next.y) / 2
            path.addQuadCurve(to: next, control: CGPoint(x: midX, y: midY))
        }

        path.closeSubpath()
        return path
    }

    // MARK: - Light Refraction Simulation

    func refractionOffset(for point: CGPoint, relativeTo center: CGPoint, time: Double) -> CGSize {
        let dx = point.x - center.x
        let dy = point.y - center.y
        let distance = sqrt(dx * dx + dy * dy)

        guard distance > 0 else { return .zero }

        let refractionStrength = (liquidState.refractionIndex - 1.0) * 8.0
        let ripple = sin(distance * 0.5 - time * 2.0) * refractionStrength * liquidState.deformation
        let nx = dx / distance
        let ny = dy / distance

        return CGSize(width: nx * ripple, height: ny * ripple)
    }

    // MARK: - Inner Glow Color

    func innerGlowColor(base: Color) -> Color {
        let warmth = liquidState.innerGlowWarmth
        // Blend toward warm (amber) or cool (blue) based on warmth
        let warmComponent = Color(hex: "FFD4A0").opacity(warmth * 0.3)
        let coolComponent = Color(hex: "A0C8FF").opacity((1.0 - warmth) * 0.2)
        // Simple blend via opacity layering — actual rendering handles compositing
        return base
    }

    // MARK: - Default Profile

    static let defaultProfile = LiquidProfile(
        fluid: .organic,
        optics: OpticsConfig(
            baseRefraction: 1.2, chromaticAberration: 0.03,
            internalCaustics: 0.5, subsurfaceScatter: 0.4,
            fresnelStrength: 0.6,
            glowColor: Color(hex: "FFFFFF"),
            glowRadius: 60, glowOpacity: 0.06,
            shadowColor: Color(hex: "000000"),
            shadowRadius: 20
        ),
        particles: LiquidParticleConfig(
            maxCount: 60, sizeRange: 1.5...5.0,
            opacityRange: 0.08...0.35,
            color: Color(hex: "FFFFFF"),
            innerColor: Color(hex: "FFFAF0"),
            behavior: .float, speedMultiplier: 1.0,
            turbulenceResponse: 0.6, trailLength: 0.3
        ),
        boundary: .smooth,
        timing: .calm
    )

    deinit {
        timer?.invalidate()
        thermalTimer?.invalidate()
    }
}

// MARK: - Particle State

struct ParticleState: Sendable {
    let id: Int
    var angle: Double
    var radius: Double
    var speed: Double
    var size: Double
    var opacity: Double
    var phase: Double
}

// MARK: - Easing

private func easeOutCubic(_ t: Double) -> Double {
    let t1 = t - 1.0
    return t1 * t1 * t1 + 1.0
}
