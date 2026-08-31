import SwiftUI

// ── Visual Physics Engine V2: 视觉物理引擎 ──
// Simulates natural physical behaviors for visual elements:
// - Spring dynamics for UI element transitions
// - Fluid drag simulation for particle systems
// - Light refraction and caustic approximations
// - Organic noise fields for natural-feeling motion
// - Gravity well simulation around the liquid core

struct VisualPhysicsEngine {
    // MARK: - Spring Simulation

    static func spring(
        current: Double,
        target: Double,
        velocity: inout Double,
        stiffness: Double = 120,
        damping: Double = 12,
        deltaTime: Double = 0.016
    ) -> Double {
        let force = (target - current) * stiffness
        let dampedForce = force - velocity * damping
        velocity += dampedForce * deltaTime
        return current + velocity * deltaTime
    }

    static func spring2D(
        current: CGPoint,
        target: CGPoint,
        velocity: inout CGPoint,
        stiffness: Double = 120,
        damping: Double = 12,
        deltaTime: Double = 0.016
    ) -> CGPoint {
        var vx = Double(velocity.x)
        var vy = Double(velocity.y)
        let x = spring(current: Double(current.x), target: Double(target.x), velocity: &vx, stiffness: stiffness, damping: damping, deltaTime: deltaTime)
        let y = spring(current: Double(current.y), target: Double(target.y), velocity: &vy, stiffness: stiffness, damping: damping, deltaTime: deltaTime)
        velocity = CGPoint(x: vx, y: vy)
        return CGPoint(x: x, y: y)
    }

    // MARK: - Fluid Drag

    static func fluidDrag(
        velocity: Double,
        viscosity: Double,   // 0.0–1.0
        deltaTime: Double = 0.016
    ) -> Double {
        let dragCoefficient = 1.0 + viscosity * 8.0
        return velocity * exp(-dragCoefficient * deltaTime)
    }

    static func fluidDrag2D(
        velocity: CGPoint,
        viscosity: Double,
        deltaTime: Double = 0.016
    ) -> CGPoint {
        CGPoint(
            x: fluidDrag(velocity: velocity.x, viscosity: viscosity, deltaTime: deltaTime),
            y: fluidDrag(velocity: velocity.y, viscosity: viscosity, deltaTime: deltaTime)
        )
    }

    // MARK: - Gravity Well

    static func gravityWell(
        position: CGPoint,
        center: CGPoint,
        mass: Double,
        minRadius: Double = 20,
        deltaTime: Double = 0.016
    ) -> CGPoint {
        let dx = center.x - position.x
        let dy = center.y - position.y
        let distance = max(minRadius, sqrt(dx * dx + dy * dy))
        let force = mass / (distance * distance)
        let maxForce: Double = 8.0
        let clampedForce = min(force, maxForce)
        return CGPoint(
            x: position.x + dx / distance * clampedForce * deltaTime * 60,
            y: position.y + dy / distance * clampedForce * deltaTime * 60
        )
    }

    // MARK: - Organic Noise Field

    /// Full 4-octave noise — high quality, more trig calls.
    static func noiseField(
        at point: CGPoint,
        time: Double,
        scale: Double = 0.01,
        strength: Double = 1.0
    ) -> CGPoint {
        // Multi-octave sinusoidal noise approximation
        let x = point.x * scale
        let y = point.y * scale
        let t = time

        let n1 = sin(x * 1.7 + t * 0.3) * cos(y * 2.1 + t * 0.4)
        let n2 = sin(x * 3.4 + y * 1.3 + t * 0.5) * 0.5
        let n3 = cos(x * 5.1 - y * 2.7 + t * 0.6) * 0.25
        let n4 = sin(x * 8.3 + y * 5.9 - t * 0.7) * 0.125

        let total = (n1 + n2 + n3 + n4) * strength
        let angle = total * .pi
        let magnitude = abs(total)

        return CGPoint(
            x: cos(angle) * magnitude * 20,
            y: sin(angle) * magnitude * 20
        )
    }

    /// Fast 2-octave noise — ~50% fewer trig calls, visually similar for ambient use.
    static func noiseFieldFast(
        at point: CGPoint,
        time: Double,
        scale: Double = 0.01,
        strength: Double = 1.0
    ) -> CGPoint {
        let x = point.x * scale
        let y = point.y * scale
        let t = time

        let n1 = sin(x * 1.7 + t * 0.3) * cos(y * 2.1 + t * 0.4)
        let n2 = sin(x * 3.4 + y * 1.3 + t * 0.5) * 0.5

        let total = (n1 + n2) * strength
        let angle = total * .pi
        let magnitude = abs(total)

        return CGPoint(
            x: cos(angle) * magnitude * 20,
            y: sin(angle) * magnitude * 20
        )
    }

    // MARK: - Light Refraction Approximation

    static func refractionDisplacement(
        point: CGPoint,
        center: CGPoint,
        refractiveIndex: Double,
        surfaceCurvature: Double,
        time: Double
    ) -> CGSize {
        let dx = point.x - center.x
        let dy = point.y - center.y
        let dist = sqrt(dx * dx + dy * dy)

        guard dist > 0 else { return .zero }

        // Snell-like bending: light bends more at edges (higher curvature)
        let edgeFactor = min(1.0, dist / 100.0)
        let bendPower = (refractiveIndex - 1.0) * surfaceCurvature * edgeFactor
        let ripple = sin(dist * 0.3 - time * 1.5) * bendPower * 12

        let nx = dx / dist
        let ny = dy / dist

        return CGSize(width: nx * ripple, height: ny * ripple)
    }

    // MARK: - Caustic Intensity

    static func causticIntensity(
        at point: CGPoint,
        center: CGPoint,
        time: Double,
        patternScale: Double = 0.05
    ) -> Double {
        let dx = point.x - center.x
        let dy = point.y - center.y
        let dist = sqrt(dx * dx + dy * dy)

        let caustic1 = sin(dist * patternScale + time * 0.8) * cos(dist * patternScale * 1.7 - time * 0.5)
        let caustic2 = sin(dx * patternScale * 2.3 + time * 0.6) * cos(dy * patternScale * 2.1 - time * 0.7)
        let caustic3 = cos((dx + dy) * patternScale * 1.5 + time * 0.4) * 0.5

        let raw = (caustic1 + caustic2 + caustic3) / 2.5
        return max(0, raw * 0.3 + 0.05)  // 0.05–0.35 range
    }

    // MARK: - Organic Breathing Curve

    static func breathCurve(
        phase: Double,
        amplitude: Double,
        asymmetry: Double = 0.0  // -1.0 (long inhale) to +1.0 (long exhale)
    ) -> Double {
        // Asymmetric sine: inhale vs exhale have different durations
        let asymmetricPhase = phase + asymmetry * sin(phase * .pi) * 0.1
        return sin(asymmetricPhase * 2 * .pi) * amplitude
    }

    // MARK: - Thermal Blur

    static func thermalBlur(
        intensity: Double,
        turbulence: Double,
        time: Double
    ) -> Double {
        let base = intensity * 20
        let variation = sin(time * 2.3) * cos(time * 1.7) * turbulence * 8
        return max(0, base + variation)
    }
}
