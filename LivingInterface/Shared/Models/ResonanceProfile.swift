import Foundation

// ── Resonance Profile V2: 音频共振配置模型 ──
// Maps audio analysis results to visual parameters.
// Defines frequency band mappings, BPM-to-breath conversion,
// and safety/privacy constraints.

// MARK: - Resonance Profile

struct ResonanceProfile: Sendable {
    let frequencyBands: FrequencyBands
    let visualMapping: ResonanceVisualMap
    let bpmMapping: BPMMapping
    let privacy: ResonancePrivacy
}

// MARK: - Frequency Bands

struct FrequencyBands: Sendable {
    let sub: ClosedRange<Double>       // 20–60 Hz
    let bass: ClosedRange<Double>      // 60–250 Hz
    let lowMid: ClosedRange<Double>    // 250–500 Hz
    let mid: ClosedRange<Double>       // 500–2000 Hz
    let highMid: ClosedRange<Double>   // 2000–4000 Hz
    let high: ClosedRange<Double>      // 4000–8000 Hz
    let air: ClosedRange<Double>       // 8000–20000 Hz

    static let standard = FrequencyBands(
        sub: 20...60, bass: 60...250,
        lowMid: 250...500, mid: 500...2000,
        highMid: 2000...4000, high: 4000...8000,
        air: 8000...20000
    )
}

// MARK: - Resonance Visual Map

struct ResonanceVisualMap: Sendable {
    let subScalePulse: Double          // how much sub affects core scale
    let bassBreathDepth: Double        // how much bass modulates breath depth
    let midColorShift: Double          // how much mid shifts hue/warmth
    let highMidParticleActivity: Double // particle sparkle response
    let highRefractionRipple: Double   // high freq refraction ripple
    let airBlurModulation: Double      // air band → glow blur modulation

    static let `default` = ResonanceVisualMap(
        subScalePulse: 0.15,
        bassBreathDepth: 0.3,
        midColorShift: 0.1,
        highMidParticleActivity: 0.4,
        highRefractionRipple: 0.2,
        airBlurModulation: 0.15
    )
}

// MARK: - BPM Mapping

struct BPMMapping: Sendable {
    let minBPM: Double
    let maxBPM: Double
    let breathRatio: Double            // breath cycles per beat

    func breathPeriod(for bpm: Double) -> Double {
        let clamped = max(minBPM, min(maxBPM, bpm))
        return 60.0 / clamped * breathRatio
    }

    func fluidSpeed(for bpm: Double) -> Double {
        let normalized = (bpm - minBPM) / (maxBPM - minBPM)
        return 0.2 + normalized * 0.8  // 0.2–1.0
    }

    static let `default` = BPMMapping(
        minBPM: 40, maxBPM: 200, breathRatio: 2.0
    )
}

// MARK: - Resonance Privacy

struct ResonancePrivacy: Sendable {
    let microphoneDefaultOff: Bool
    let audioUploadProhibited: Bool
    let audioSaveProhibited: Bool
    let localAnalysisOnly: Bool
    let fftWindowSize: Int
    let sampleRate: Double
    let requiresUserConsent: Bool

    static let strict = ResonancePrivacy(
        microphoneDefaultOff: true,
        audioUploadProhibited: true,
        audioSaveProhibited: true,
        localAnalysisOnly: true,
        fftWindowSize: 2048,
        sampleRate: 44100,
        requiresUserConsent: true
    )
}

// MARK: - Audio Analysis Snapshot

struct AudioSnapshot: Sendable {
    let timestamp: Date
    let bpm: Double
    let rmsAmplitude: Double           // 0.0–1.0
    let spectralCentroid: Double       // brightness
    let bandEnergies: [String: Double] // keyed by band name
    let beatStrength: Double           // 0.0–1.0, onset detection
    let isBeat: Bool

    static let silent = AudioSnapshot(
        timestamp: Date(),
        bpm: 0,
        rmsAmplitude: 0,
        spectralCentroid: 0,
        bandEnergies: [:],
        beatStrength: 0,
        isBeat: false
    )
}

// MARK: - Resonance State

struct ResonanceState: Sendable {
    var breathPeriodModifier: Double   // multiplies base breath period
    var fluidSpeedModifier: Double     // multiplies base fluid speed
    var glowIntensityModifier: Double  // adds to base glow
    var particleActivityModifier: Double
    var colorWarmthShift: Double       // -0.3 (cool) ... +0.3 (warm)
    var refractionRipple: Double       // 0.0–1.0
    var blurModifier: Double           // adds to blur radius

    static let neutral = ResonanceState(
        breathPeriodModifier: 1.0,
        fluidSpeedModifier: 1.0,
        glowIntensityModifier: 0.0,
        particleActivityModifier: 1.0,
        colorWarmthShift: 0.0,
        refractionRipple: 0.0,
        blurModifier: 0.0
    )
}
