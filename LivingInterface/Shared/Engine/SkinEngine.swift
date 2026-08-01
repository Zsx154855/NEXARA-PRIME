import SwiftUI

@MainActor final class SkinEngine: ObservableObject {
    @Published var activeSkin: LifeSkin = .morningMist

    func profile(for skin: LifeSkin) -> SkinProfile {
        let c = SkinProfile.defaultColors(for: skin)
        let l = SkinProfile.defaultLighting(for: skin)
        let d = SkinProfile.defaultDynamics(for: skin)
        let p = SkinProfile.defaultParticles(for: skin)
        let map = skin == .galaxy ? Self.defaultStateMapGalaxy(baseColor: c.primary) : Self.defaultStateMap(baseColor: c.primary)
        return SkinProfile(skin: skin, colors: c, lighting: l, dynamics: d, particles: p,
            stateMap: map, liquidProfile: nil)
    }
    static func defaultStateMap(baseColor: Color) -> [LivingState: StateSkinMapping] {[
        .silent: StateSkinMapping(coreColor: Color(hex: "D8D2CA"), coreAnimation: .lowBreath, particleMultiplier: 1.0, glowIntensity: 0.3, liquidDeformation: 0.0),
        .thinking: StateSkinMapping(coreColor: Color(hex: "C49A55"), coreAnimation: .fluidConverge, particleMultiplier: 1.5, glowIntensity: 0.6, liquidDeformation: 0.3),
        .planning: StateSkinMapping(coreColor: Color(hex: "D58F98"), coreAnimation: .fluidConverge, particleMultiplier: 1.3, glowIntensity: 0.5, liquidDeformation: 0.25),
        .executing: StateSkinMapping(coreColor: Color(hex: "72865D"), coreAnimation: .energyDiffuse, particleMultiplier: 2.0, glowIntensity: 0.8, liquidDeformation: 0.6),
        .learning: StateSkinMapping(coreColor: Color(hex: "B8A890"), coreAnimation: .nodeGrowth, particleMultiplier: 1.3, glowIntensity: 0.5, liquidDeformation: 0.4),
        .awaitingApproval: StateSkinMapping(coreColor: Color(hex: "D58F98"), coreAnimation: .awaitPulse, particleMultiplier: 0.5, glowIntensity: 0.9, liquidDeformation: 0.0),
        .recovery: StateSkinMapping(coreColor: Color(hex: "C49A55"), coreAnimation: .lowBreath, particleMultiplier: 1.0, glowIntensity: 0.5, liquidDeformation: 0.2),
    ]}
    static func defaultStateMapGalaxy(baseColor _: Color) -> [LivingState: StateSkinMapping] {[
        .silent: StateSkinMapping(coreColor: Color(hex: "D0D7DE"), coreAnimation: .lowBreath, particleMultiplier: 0.6, glowIntensity: 0.15, liquidDeformation: 0.0),
        .thinking: StateSkinMapping(coreColor: Color(hex: "0969DA"), coreAnimation: .fluidConverge, particleMultiplier: 1.0, glowIntensity: 0.4, liquidDeformation: 0.2),
        .planning: StateSkinMapping(coreColor: Color(hex: "6E40C9"), coreAnimation: .fluidConverge, particleMultiplier: 0.8, glowIntensity: 0.35, liquidDeformation: 0.18),
        .executing: StateSkinMapping(coreColor: Color(hex: "22863A"), coreAnimation: .energyDiffuse, particleMultiplier: 1.5, glowIntensity: 0.6, liquidDeformation: 0.5),
        .learning: StateSkinMapping(coreColor: Color(hex: "6E40C9"), coreAnimation: .nodeGrowth, particleMultiplier: 1.0, glowIntensity: 0.35, liquidDeformation: 0.3),
        .awaitingApproval: StateSkinMapping(coreColor: Color(hex: "E36209"), coreAnimation: .awaitPulse, particleMultiplier: 0.4, glowIntensity: 0.7, liquidDeformation: 0.0),
        .recovery: StateSkinMapping(coreColor: Color(hex: "0969DA"), coreAnimation: .lowBreath, particleMultiplier: 0.7, glowIntensity: 0.35, liquidDeformation: 0.15),
    ]}
    func switchSkin(to skin: LifeSkin) { withAnimation(.easeInOut(duration: profile(for: activeSkin).dynamics.transitionSpeed)) { activeSkin = skin } }
    func stateMapping(for state: LivingState) -> StateSkinMapping { profile(for: activeSkin).stateMap[state] ?? Self.defaultStateMap(baseColor: activeSkin.primary)[state]! }
    func spatialTheme() -> SpatialTheme { .default }
}

struct SkinProfile {
    let skin: LifeSkin; let colors: SkinColors; let lighting: SkinLighting
    let dynamics: SkinDynamics; let particles: ParticleConfig
    let stateMap: [LivingState: StateSkinMapping]; let liquidProfile: LiquidProfile?

    static func defaultColors(for skin: LifeSkin) -> SkinColors {
        switch skin {
        case .morningMist: return SkinColors(background: Color(hex: "F5F0E8"), primary: Color(hex: "D8D2CA"), secondary: Color(hex: "ECE8E2"), accent: Color(hex: "C49A55"), textPrimary: Color(hex: "302F2D"), textSecondary: Color(hex: "6B6560"))
        case .tide: return SkinColors(background: Color(hex: "F5F0E8"), primary: Color(hex: "C49A55"), secondary: Color(hex: "D8C8A0"), accent: Color(hex: "D58F98"), textPrimary: Color(hex: "302F2D"), textSecondary: Color(hex: "6B6560"))
        case .forestBreath: return SkinColors(background: Color(hex: "F5F0E8"), primary: Color(hex: "72865D"), secondary: Color(hex: "A8B898"), accent: Color(hex: "C49A55"), textPrimary: Color(hex: "302F2D"), textSecondary: Color(hex: "6B6560"))
        case .sunsetGlow: return SkinColors(background: Color(hex: "F5F0E8"), primary: Color(hex: "D58F98"), secondary: Color(hex: "E8C8C8"), accent: Color(hex: "C49A55"), textPrimary: Color(hex: "302F2D"), textSecondary: Color(hex: "6B6560"))
        case .galaxy: return SkinColors(background: Color(hex: "F6F8FA"), primary: Color(hex: "0969DA"), secondary: Color(hex: "D0D7DE"), accent: Color(hex: "6E40C9"), textPrimary: Color(hex: "24292F"), textSecondary: Color(hex: "57606A"))
        }
    }
    static func defaultLighting(for skin: LifeSkin) -> SkinLighting {
        switch skin {
        case .morningMist: return SkinLighting(ambientIntensity: 0.6, glowRadius: 60, glowOpacity: 0.04, warmth: 0.7, subsurfaceIntensity: 0.5, fresnelStrength: 0.3, volumetricDensity: 0.5)
        case .tide: return SkinLighting(ambientIntensity: 0.5, glowRadius: 80, glowOpacity: 0.05, warmth: 0.6, subsurfaceIntensity: 0.5, fresnelStrength: 0.3, volumetricDensity: 0.5)
        case .forestBreath: return SkinLighting(ambientIntensity: 0.55, glowRadius: 50, glowOpacity: 0.03, warmth: 0.6, subsurfaceIntensity: 0.5, fresnelStrength: 0.3, volumetricDensity: 0.5)
        case .sunsetGlow: return SkinLighting(ambientIntensity: 0.7, glowRadius: 70, glowOpacity: 0.06, warmth: 0.85, subsurfaceIntensity: 0.5, fresnelStrength: 0.3, volumetricDensity: 0.5)
        case .galaxy: return SkinLighting(ambientIntensity: 0.45, glowRadius: 50, glowOpacity: 0.02, warmth: 0.3, subsurfaceIntensity: 0.4, fresnelStrength: 0.2, volumetricDensity: 0.4)
        }
    }
    static func defaultDynamics(for skin: LifeSkin) -> SkinDynamics {
        switch skin {
        case .morningMist: return SkinDynamics(breathPeriod: 4.0, transitionSpeed: 1.2, particleSpeed: 0.3, responsiveness: 0.8)
        case .tide: return SkinDynamics(breathPeriod: 6.0, transitionSpeed: 1.8, particleSpeed: 0.2, responsiveness: 0.6)
        case .forestBreath: return SkinDynamics(breathPeriod: 5.0, transitionSpeed: 1.0, particleSpeed: 0.35, responsiveness: 0.75)
        case .sunsetGlow: return SkinDynamics(breathPeriod: 4.5, transitionSpeed: 1.5, particleSpeed: 0.25, responsiveness: 0.7)
        case .galaxy: return SkinDynamics(breathPeriod: 5.0, transitionSpeed: 0.8, particleSpeed: 0.15, responsiveness: 0.9)
        }
    }
    static func defaultParticles(for skin: LifeSkin) -> ParticleConfig {
        switch skin {
        case .morningMist: return ParticleConfig(count: 12, size: 2...6, opacity: 0.1...0.3, color: Color(hex: "D8D2CA"), behavior: .float)
        case .tide: return ParticleConfig(count: 20, size: 2...5, opacity: 0.08...0.25, color: Color(hex: "C49A55"), behavior: .rise)
        case .forestBreath: return ParticleConfig(count: 16, size: 3...7, opacity: 0.1...0.35, color: Color(hex: "72865D"), behavior: .orbit)
        case .sunsetGlow: return ParticleConfig(count: 14, size: 2...6, opacity: 0.12...0.35, color: Color(hex: "D58F98"), behavior: .pulse)
        case .galaxy: return ParticleConfig(count: 8, size: 1...3, opacity: 0.06...0.15, color: Color(hex: "0969DA"), behavior: .float)
        }
    }
}
struct SkinColors { let background,primary,secondary,accent,textPrimary,textSecondary: Color
    var glassOverlay: Color { Color.white.opacity(0.3) }; var shadow: Color { primary.opacity(0.15) }
    var deepGlow: Color { Color.white.opacity(0.1) }; var particleInner: Color { Color.white.opacity(0.3) }
    var membraneHighlight: Color { Color.white.opacity(0.2) }; var ambientTint: Color { primary.opacity(0.1) }
}
struct SkinLighting { let ambientIntensity,glowRadius,glowOpacity,warmth,subsurfaceIntensity,fresnelStrength,volumetricDensity: Double }
struct SkinDynamics { let breathPeriod,transitionSpeed,particleSpeed,responsiveness: Double }
struct ParticleConfig { let count: Int; let size: ClosedRange<Double>; let opacity: ClosedRange<Double>; let color: Color; let behavior: ParticleBehavior }
enum ParticleBehavior: String { case float, rise, orbit, pulse }
struct StateSkinMapping { let coreColor: Color; let coreAnimation: CoreAnimationType; let particleMultiplier: Double; let glowIntensity: Double; let liquidDeformation: Double }
enum CoreAnimationType: String { case lowBreath, fluidConverge, energyDiffuse, nodeGrowth, awaitPulse }
