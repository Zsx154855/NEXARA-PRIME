import Foundation
import AVFoundation
import Accelerate

// ── Audio Resonance Engine V2: 音乐共振系统 ──
// Local-only audio analysis: BPM detection, spectral analysis,
// onset detection. Maps audio features to visual parameters.
// Privacy: default mic OFF, no upload, no save, local FFT only.

@MainActor
final class AudioResonanceEngine: ObservableObject {
    // ── Published State ──
    @Published var isRunning: Bool = false
    @Published var microphoneEnabled: Bool = false
    @Published var currentBPM: Double = 0
    @Published var rmsAmplitude: Double = 0
    @Published var bandEnergies: [String: Double] = [:]
    @Published var resonanceState: ResonanceState = .neutral
    @Published var latestSnapshot: AudioSnapshot = .silent
    @Published var userConsentGiven: Bool = false

    // ── Configuration ──
    private let privacy = ResonancePrivacy.strict
    private let frequencyBands = FrequencyBands.standard
    private let visualMap = ResonanceVisualMap.default
    private let bpmMapping = BPMMapping.default

    // ── Audio Engine ──
    private var audioEngine: AVAudioEngine?
    private var inputNode: AVAudioInputNode?
    private let fftSize = 2048
    private let hopSize = 512
    private var fftSetup: FFTSetup?
    private var bpmDetector: BPMDetector?

    // ── State ──
    private var analysisTimer: Timer?
    private var energyHistory: [Double] = []
    private let historyLength = 100

    // MARK: - Lifecycle

    init() {
        fftSetup = vDSP_create_fftsetup(vDSP_Length(log2(Float(fftSize))), FFTRadix(kFFTRadix2))
        bpmDetector = BPMDetector()
    }

    // MARK: - Microphone Control

    func requestMicrophoneAccess() async -> Bool {
        guard privacy.requiresUserConsent else { return false }

        #if os(macOS)
        return await withCheckedContinuation { continuation in
            switch AVCaptureDevice.authorizationStatus(for: .audio) {
            case .authorized:
                continuation.resume(returning: true)
            case .notDetermined:
                AVCaptureDevice.requestAccess(for: .audio) { granted in
                    continuation.resume(returning: granted)
                }
            default:
                continuation.resume(returning: false)
            }
        }
        #elseif os(iOS)
        switch AVAudioApplication.shared.recordPermission {
        case .granted:
            return true
        case .undetermined:
            return await AVAudioApplication.requestRecordPermission()
        @unknown default:
            return false
        }
        #else
        return false
        #endif
    }

    func startMicrophone() async {
        guard privacy.localAnalysisOnly else { return }
        guard userConsentGiven else { return }

        let authorized = await requestMicrophoneAccess()
        guard authorized else { return }

        do {
            audioEngine = AVAudioEngine()
            guard let engine = audioEngine else { return }
            inputNode = engine.inputNode

            let format = inputNode!.outputFormat(forBus: 0)
            let analysisFormat = AVAudioFormat(
                standardFormatWithSampleRate: privacy.sampleRate,
                channels: 1
            )!

            guard let fftSetup else { return }

            inputNode!.installTap(onBus: 0, bufferSize: AVAudioFrameCount(fftSize),
                                   format: format) { [weak self] buffer, _ in
                self?.processAudioBuffer(buffer, format: analysisFormat, fftSetup: fftSetup)
            }

            try engine.start()
            microphoneEnabled = true
            isRunning = true
            startAnalysisTimer()
        } catch {
            microphoneEnabled = false
            isRunning = false
        }
    }

    func stopMicrophone() {
        audioEngine?.stop()
        audioEngine?.inputNode.removeTap(onBus: 0)
        audioEngine = nil
        inputNode = nil
        microphoneEnabled = false
        isRunning = false
        analysisTimer?.invalidate()
        analysisTimer = nil
    }

    func grantConsent() {
        userConsentGiven = true
    }

    func revokeConsent() {
        userConsentGiven = false
        stopMicrophone()
    }

    // MARK: - Audio Processing

    private func processAudioBuffer(_ buffer: AVAudioPCMBuffer, format: AVAudioFormat, fftSetup: FFTSetup) {
        guard let channelData = buffer.floatChannelData else { return }
        let frameLength = Int(buffer.frameLength)
        let samples = Array(UnsafeBufferPointer(start: channelData[0], count: frameLength))

        // RMS Amplitude
        var rms: Float = 0
        vDSP_rmsqv(samples, 1, &rms, vDSP_Length(frameLength))
        let amplitude = Double(rms)

        // FFT
        let log2n = vDSP_Length(log2(Float(fftSize)))
        let n = fftSize / 2

        var realParts = [Float](repeating: 0, count: n)
        var imagParts = [Float](repeating: 0, count: n)

        samples.withUnsafeBufferPointer { samplesPtr in
            var splitComplex = DSPSplitComplex(realp: &realParts, imagp: &imagParts)
            samplesPtr.baseAddress?.withMemoryRebound(to: DSPComplex.self, capacity: n) { complexPtr in
                vDSP_ctoz(complexPtr, 2, &splitComplex, 1, vDSP_Length(n))
            }
        }

        // Hann window
        var window = [Float](repeating: 0, count: n)
        vDSP_hann_window(&window, vDSP_Length(n), Int32(vDSP_HANN_NORM))
        vDSP_vmul(realParts, 1, window, 1, &realParts, 1, vDSP_Length(n))
        vDSP_vmul(imagParts, 1, window, 1, &imagParts, 1, vDSP_Length(n))

        var splitComplex = DSPSplitComplex(realp: &realParts, imagp: &imagParts)
        vDSP_fft_zrip(fftSetup, &splitComplex, 1, log2n, FFTDirection(kFFTDirection_Forward))

        // Magnitude spectrum
        var magnitudes = [Float](repeating: 0, count: n)
        vDSP_zvmags(&splitComplex, 1, &magnitudes, 1, vDSP_Length(n))

        // Band energies
        let sampleRate = privacy.sampleRate
        var energies: [String: Double] = [:]
        let bands: [(String, ClosedRange<Double>)] = [
            ("sub", frequencyBands.sub),
            ("bass", frequencyBands.bass),
            ("lowMid", frequencyBands.lowMid),
            ("mid", frequencyBands.mid),
            ("highMid", frequencyBands.highMid),
            ("high", frequencyBands.high),
            ("air", frequencyBands.air),
        ]
        for (name, range) in bands {
            energies[name] = bandEnergy(magnitudes: magnitudes, sampleRate: sampleRate, range: range)
        }

        // BPM detection via onset energy
        bpmDetector?.feed(energy: amplitude)

        Task { @MainActor in
            self.rmsAmplitude = amplitude
            self.bandEnergies = energies
            self.currentBPM = bpmDetector?.currentBPM ?? 0
            self.latestSnapshot = AudioSnapshot(
                timestamp: Date(),
                bpm: currentBPM,
                rmsAmplitude: amplitude,
                spectralCentroid: computeSpectralCentroid(magnitudes: magnitudes, sampleRate: sampleRate),
                bandEnergies: energies,
                beatStrength: bpmDetector?.beatStrength ?? 0,
                isBeat: bpmDetector?.isBeat ?? false
            )
        }
    }

    // MARK: - Band Energy

    private func bandEnergy(magnitudes: [Float], sampleRate: Double, range: ClosedRange<Double>) -> Double {
        let binWidth = sampleRate / Double(fftSize)
        let lowBin = max(0, Int(range.lowerBound / binWidth))
        let highBin = min(magnitudes.count - 1, Int(range.upperBound / binWidth))
        guard lowBin <= highBin else { return 0 }

        var sum: Float = 0
        for i in lowBin...highBin {
            sum += magnitudes[i]
        }
        return Double(sum) / Double(highBin - lowBin + 1)
    }

    private func computeSpectralCentroid(magnitudes: [Float], sampleRate: Double) -> Double {
        let binWidth = sampleRate / Double(fftSize)
        var weightedSum: Double = 0
        var totalMag: Double = 0
        for (i, mag) in magnitudes.enumerated() {
            let freq = Double(i) * binWidth
            weightedSum += freq * Double(mag)
            totalMag += Double(mag)
        }
        return totalMag > 0 ? weightedSum / totalMag : 0
    }

    // MARK: - Analysis Timer

    private func startAnalysisTimer() {
        analysisTimer = Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.updateResonanceState()
            }
        }
    }

    private func updateResonanceState() {
        var state = ResonanceState.neutral

        // BPM → breath period
        if currentBPM > 0 {
            state.breathPeriodModifier = bpmMapping.breathPeriod(for: currentBPM) / 4.0
            state.fluidSpeedModifier = bpmMapping.fluidSpeed(for: currentBPM)
        }

        // Band energy → visual parameters
        let sub = bandEnergies["sub"] ?? 0
        let bass = bandEnergies["bass"] ?? 0
        let mid = bandEnergies["mid"] ?? 0
        let highMid = bandEnergies["highMid"] ?? 0
        let high = bandEnergies["high"] ?? 0
        let air = bandEnergies["air"] ?? 0

        let maxEnergy = max(1.0, [sub, bass, mid, highMid, high, air].max() ?? 1.0)

        state.glowIntensityModifier = (sub / maxEnergy) * visualMap.subScalePulse
        state.breathPeriodModifier *= 1.0 + (bass / maxEnergy) * visualMap.bassBreathDepth
        state.colorWarmthShift = (mid / maxEnergy) * visualMap.midColorShift
        state.particleActivityModifier = 1.0 + (highMid / maxEnergy) * visualMap.highMidParticleActivity
        state.refractionRipple = (high / maxEnergy) * visualMap.highRefractionRipple
        state.blurModifier = (air / maxEnergy) * visualMap.airBlurModulation * 10.0

        resonanceState = state
    }

    // MARK: - Beat Detection

    func isOnBeat(tolerance: Double = 0.1) -> Bool {
        latestSnapshot.isBeat
    }

    deinit {
        audioEngine?.stop()
        audioEngine?.inputNode.removeTap(onBus: 0)
        analysisTimer?.invalidate()
        if let fftSetup {
            vDSP_destroy_fftsetup(fftSetup)
        }
    }
}

// MARK: - BPM Detector

private final class BPMDetector {
    private var energyBuffer: [Double] = []
    private let bufferSize = 2048
    private var lastBeatTime: Date = .distantPast
    private var beatIntervals: [Double] = []
    private let maxIntervals = 20

    var currentBPM: Double = 0
    var beatStrength: Double = 0
    var isBeat: Bool = false

    func feed(energy: Double) {
        energyBuffer.append(energy)
        if energyBuffer.count > bufferSize {
            energyBuffer.removeFirst()
        }

        detectOnset(energy: energy)
    }

    private func detectOnset(energy: Double) {
        let windowSize = 43  // ~10ms at 44100Hz with hop 512
        guard energyBuffer.count >= windowSize * 2 else { return }

        let localMean = energyBuffer.suffix(windowSize).reduce(0, +) / Double(windowSize)
        let globalMean = energyBuffer.suffix(windowSize * 2).reduce(0, +) / Double(windowSize * 2)
        let threshold = globalMean * 1.4

        if energy > threshold && energy > localMean * 1.2 {
            let now = Date()
            let interval = now.timeIntervalSince(lastBeatTime)

            if interval > 0.3 {  // Max ~200 BPM
                isBeat = true
                beatStrength = min(1.0, energy / (threshold * 2))

                if interval < 2.0 {  // Min ~30 BPM
                    beatIntervals.append(interval)
                    if beatIntervals.count > maxIntervals {
                        beatIntervals.removeFirst()
                    }
                }

                if !beatIntervals.isEmpty {
                    let avgInterval = beatIntervals.reduce(0, +) / Double(beatIntervals.count)
                    currentBPM = 60.0 / avgInterval
                }

                lastBeatTime = now
                return
            }
        }

        isBeat = false
    }
}
