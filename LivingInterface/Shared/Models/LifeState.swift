import SwiftUI

// ── Life State V2 Extensions: 生命状态扩展模型 ──
// V2 additions: LiquidCoreState, SpatialPosition.
// Base enums (LivingState, LifeSkin, Color, AudioConfig) defined in LivingModels.swift.

// MARK: - Liquid Core State (V2 new)

struct LiquidCoreState: Sendable {
    var deformation: Double          // 0.0 (rigid) – 1.0 (fluid)
    var boundaryComplexity: Int      // 3–12 vertices for organic shape
    var internalParticleCount: Int   // particles inside the core
    var refractionIndex: Double      // 1.0 (clear) – 1.6 (dense glass)
    var breathAmplitude: Double      // 0.0–1.0
    var breathFrequency: Double      // cycles per second
    var fluidViscosity: Double       // 0.0 (water) – 1.0 (honey)
    var surfaceTension: Double       // 0.0 (spread) – 1.0 (tight sphere)
    var innerGlowWarmth: Double      // 0.0 (cool blue) – 1.0 (warm amber)
    var coreOpacity: Double          // 0.0–1.0

    static let `default` = LiquidCoreState(
        deformation: 0.3, boundaryComplexity: 6, internalParticleCount: 20,
        refractionIndex: 1.2, breathAmplitude: 0.15, breathFrequency: 0.25,
        fluidViscosity: 0.4, surfaceTension: 0.7,
        innerGlowWarmth: 0.6, coreOpacity: 0.85
    )

    static let silent = LiquidCoreState(
        deformation: 0.12, boundaryComplexity: 8, internalParticleCount: 10,
        refractionIndex: 1.1, breathAmplitude: 0.06, breathFrequency: 0.125,
        fluidViscosity: 0.7, surfaceTension: 0.88,
        innerGlowWarmth: 0.65, coreOpacity: 0.65
    )

    static let thinking = LiquidCoreState(
        deformation: 0.5, boundaryComplexity: 6, internalParticleCount: 30,
        refractionIndex: 1.4, breathAmplitude: 0.2, breathFrequency: 0.5,
        fluidViscosity: 0.3, surfaceTension: 0.5,
        innerGlowWarmth: 0.45, coreOpacity: 0.9
    )
    
    static let planning = LiquidCoreState(
        deformation: 0.4, boundaryComplexity: 7, internalParticleCount: 24,
        refractionIndex: 1.3, breathAmplitude: 0.16, breathFrequency: 0.35,
        fluidViscosity: 0.4, surfaceTension: 0.6,
        innerGlowWarmth: 0.55, coreOpacity: 0.88
    )

    static let executing = LiquidCoreState(
        deformation: 0.7, boundaryComplexity: 10, internalParticleCount: 45,
        refractionIndex: 1.5, breathAmplitude: 0.3, breathFrequency: 1.0,
        fluidViscosity: 0.15, surfaceTension: 0.3,
        innerGlowWarmth: 0.4, coreOpacity: 0.95
    )

    static let learning = LiquidCoreState(
        deformation: 0.55, boundaryComplexity: 8, internalParticleCount: 35,
        refractionIndex: 1.35, breathAmplitude: 0.18, breathFrequency: 0.4,
        fluidViscosity: 0.35, surfaceTension: 0.55,
        innerGlowWarmth: 0.55, coreOpacity: 0.88
    )

    static let awaitingApproval = LiquidCoreState(
        deformation: 0.08, boundaryComplexity: 5, internalParticleCount: 6,
        refractionIndex: 1.05, breathAmplitude: 0.22, breathFrequency: 0.3,
        fluidViscosity: 0.85, surfaceTension: 0.92,
        innerGlowWarmth: 0.85, coreOpacity: 0.7
    )
    
    static let recovery = LiquidCoreState(
        deformation: 0.35, boundaryComplexity: 7, internalParticleCount: 18,
        refractionIndex: 1.25, breathAmplitude: 0.14, breathFrequency: 0.3,
        fluidViscosity: 0.5, surfaceTension: 0.65,
        innerGlowWarmth: 0.5, coreOpacity: 0.82
    )
    static let galaxy = LiquidCoreState(
        deformation: 0.2, boundaryComplexity: 12, internalParticleCount: 16,
        refractionIndex: 1.15, breathAmplitude: 0.08, breathFrequency: 0.2,
        fluidViscosity: 0.55, surfaceTension: 0.8,
        innerGlowWarmth: 0.3, coreOpacity: 0.78
    )
}

// MARK: - Spatial Position (V2 new)

struct SpatialPosition: Sendable {
    var x: Double  // -1.0...1.0 (normalized space)
    var y: Double
    var z: Double  // depth: 0.0 (front) – 1.0 (back)
    var orbitRadius: Double
    var orbitAngle: Double
    var orbitSpeed: Double
    var scale: Double  // 0.5–2.0

    static let center = SpatialPosition(
        x: 0, y: 0, z: 0, orbitRadius: 0, orbitAngle: 0, orbitSpeed: 0, scale: 1.0
    )

    static func orbital(radius: Double, angle: Double, speed: Double, depth: Double) -> SpatialPosition {
        SpatialPosition(
            x: cos(angle) * radius, y: sin(angle) * radius, z: depth,
            orbitRadius: radius, orbitAngle: angle, orbitSpeed: speed,
            scale: 0.6 + (1.0 - depth) * 0.4
        )
    }
}
