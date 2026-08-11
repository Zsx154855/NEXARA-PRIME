import SwiftUI

// ── Mission Orbit View V2: 任务轨迹可视化 ──
// Orbiting mission/task nodes with trailing paths.
// Shows active tasks, queued tasks, and completed tasks
// as distinct orbital tracks with motion trails.

struct MissionOrbitView: View {
    @ObservedObject var engine: LivingEngine
    let center: CGPoint
    let coreRadius: CGFloat

    private var spatial: SpatialBrainEngine { engine.spatialBrain }
    private var theme: SpatialTheme { engine.skinEngine.spatialTheme() }
    private var profile: SkinProfile { engine.skinProfile }

    var body: some View {
        ZStack {
            ForEach(spatial.missionOrbits) { orbit in
                missionOrbitGroup(orbit)
            }
        }
        .accessibilityLabel("任务轨迹，\(spatial.missionOrbits.count) 个任务轨道")
    }

    // MARK: - Mission Orbit Group

    private func missionOrbitGroup(_ orbit: SpatialBrainEngine.MissionOrbit) -> some View {
        ZStack {
            // Trail dots
            ForEach(Array(orbit.trailPositions(center: center).enumerated()), id: \.offset) { idx, pos in
                let trailOpacity = orbit.opacity * (1.0 - Double(idx) / Double(orbit.trailLength + 1)) * 0.5
                let trailSize = 4.0 - Double(idx) * 0.5
                Circle()
                    .fill(theme.orbitTrailColor.opacity(trailOpacity))
                    .frame(width: trailSize, height: trailSize)
                    .position(pos)
            }

            // Main mission node
            Circle()
                .fill(profile.colors.accent.opacity(orbit.opacity * 0.7))
                .frame(width: 10, height: 10)
                .overlay(
                    Circle()
                        .stroke(profile.colors.primary.opacity(orbit.opacity), lineWidth: 1.5)
                )
                .position(orbit.position(center: center))

            // Mission label
            Text(orbit.label)
                .font(.system(size: 8, weight: .medium))
                .foregroundColor(profile.colors.textSecondary)
                .position(
                    x: orbit.position(center: center).x,
                    y: orbit.position(center: center).y + 14
                )
                .opacity(orbit.opacity * 0.6)
        }
    }
}
