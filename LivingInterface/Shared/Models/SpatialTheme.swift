import SwiftUI

/// Spatial theme colors for V2 visual elements — Warm Ivory palette.
struct SpatialTheme {
    let controlPlaneTint: Color
    let panelBackground: Color
    let accentGlow: Color
    let criticalBorder: Color
    let approveTint: Color
    let rejectTint: Color
    let pauseTint: Color
    let galaxyAccent: Color
    let gridLineOpacity: Double
    let nodeGlowColor: Color
    let orbitTint: Color
    let orbitTrailColor: Color
    let coreGlowColor: Color

    static let `default` = SpatialTheme(
        controlPlaneTint: Color(hex: "C49A55"),
        panelBackground: Color(hex: "F5F0E8").opacity(0.92),
        accentGlow: Color(hex: "D58F98").opacity(0.25),
        criticalBorder: Color(hex: "D48888"),
        approveTint: Color(hex: "6BA87A"),
        rejectTint: Color(hex: "D48888"),
        pauseTint: Color(hex: "E0C8B0"),
        galaxyAccent: Color(hex: "C49A55").opacity(0.3),
        gridLineOpacity: 0.10,
        nodeGlowColor: Color.white.opacity(0.45),
        orbitTint: Color(hex: "D8D2CA").opacity(0.25),
        orbitTrailColor: Color.white.opacity(0.35),
        coreGlowColor: Color(hex: "D58F98").opacity(0.2)
    )
}
