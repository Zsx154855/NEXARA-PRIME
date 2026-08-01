import SwiftUI

// ── Liquid Profile V2: 液态核心配置模型 ──
// Configuration profiles for the liquid core rendering engine.
// Each profile defines fluid dynamics, optical properties,
// and particle system parameters.

// MARK: - Liquid Profile

struct LiquidProfile: Sendable {
    let fluid: FluidConfig
    let optics: OpticsConfig
    let particles: LiquidParticleConfig
    let boundary: BoundaryConfig
    let timing: LiquidTimingConfig
}

// MARK: - Fluid Configuration

struct FluidConfig: Sendable {
    let viscosity: Double          // 0.0 (water) – 1.0 (honey)
    let surfaceTension: Double     // 0.0 (spread flat) – 1.0 (tight sphere)
    let turbulence: Double         // 0.0 (laminar flow) – 1.0 (chaotic)
    let density: Double            // 0.5–2.0, affects refraction
    let restingShape: Double       // 0.0 (flat) – 1.0 (sphere)

    static let water = FluidConfig(
        viscosity: 0.1, surfaceTension: 0.6,
        turbulence: 0.2, density: 1.0, restingShape: 0.8
    )

    static let glass = FluidConfig(
        viscosity: 0.7, surfaceTension: 0.9,
        turbulence: 0.05, density: 1.5, restingShape: 0.95
    )

    static let organic = FluidConfig(
        viscosity: 0.4, surfaceTension: 0.5,
        turbulence: 0.4, density: 1.1, restingShape: 0.65
    )
}

// MARK: - Optics Configuration

struct OpticsConfig: Sendable {
    let baseRefraction: Double      // 1.0–1.6
    let chromaticAberration: Double // 0.0–0.1
    let internalCaustics: Double    // 0.0–1.0
    let subsurfaceScatter: Double   // 0.0–1.0
    let fresnelStrength: Double     // 0.0–1.0
    let glowColor: Color
    let glowRadius: Double          // blur radius in points
    let glowOpacity: Double         // 0.0–1.0
    let shadowColor: Color
    let shadowRadius: Double
}

// MARK: - Liquid Particle Configuration

struct LiquidParticleConfig: Sendable {
    let maxCount: Int
    let sizeRange: ClosedRange<Double>
    let opacityRange: ClosedRange<Double>
    let color: Color
    let innerColor: Color
    let behavior: LiquidParticleBehavior
    let speedMultiplier: Double     // 0.0–2.0
    let turbulenceResponse: Double  // 0.0 (ignore) – 1.0 (full)
    let trailLength: Double         // 0.0–1.0
}

enum LiquidParticleBehavior: String, Sendable {
    case float = "float"             // slow drift with Brownian motion
    case rise = "rise"               // buoyant upward drift
    case orbit = "orbit"             // circular around core center
    case pulse = "pulse"             // radial in/out breathing
    case flow = "flow"               // follow fluid streamlines
    case converge = "converge"       // draw inward toward center
    case diffuse = "diffuse"         // radiate outward from center
    case swarm = "swarm"             // organic group movement
}

// MARK: - Boundary Configuration

struct BoundaryConfig: Sendable {
    let vertexCount: Int             // 3–12, organic polygon
    let deformationAmplitude: Double // 0.0–1.0
    let deformationFrequency: Double // cycles
    let edgeSoftness: Double         // 0.0 (hard) – 1.0 (blurred)
    let membraneThickness: Double    // stroke width
    let membraneColor: Color
    let membraneOpacity: Double

    static let smooth = BoundaryConfig(
        vertexCount: 6, deformationAmplitude: 0.3,
        deformationFrequency: 0.5, edgeSoftness: 0.7,
        membraneThickness: 1.5,
        membraneColor: .white, membraneOpacity: 0.3
    )

    static let organic = BoundaryConfig(
        vertexCount: 10, deformationAmplitude: 0.6,
        deformationFrequency: 1.2, edgeSoftness: 0.5,
        membraneThickness: 2.0,
        membraneColor: .white, membraneOpacity: 0.2
    )
}

// MARK: - Liquid Timing Configuration

struct LiquidTimingConfig: Sendable {
    let breathPeriod: Double         // seconds per full breath cycle
    let deformationSpeed: Double     // 0.5–3.0, how fast shape changes
    let particleUpdateRate: Double   // seconds between particle recalc
    let stateTransitionDuration: Double // seconds
    let thermalEquilibriumTime: Double  // seconds to stabilize after state change

    static let calm = LiquidTimingConfig(
        breathPeriod: 4.0, deformationSpeed: 0.8,
        particleUpdateRate: 0.05, stateTransitionDuration: 1.2,
        thermalEquilibriumTime: 3.0
    )

    static let active = LiquidTimingConfig(
        breathPeriod: 2.0, deformationSpeed: 1.5,
        particleUpdateRate: 0.033, stateTransitionDuration: 0.6,
        thermalEquilibriumTime: 1.5
    )
}
