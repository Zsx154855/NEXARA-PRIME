import SwiftUI

// ── Living State ──
enum LivingState: String, CaseIterable, Codable {
    case silent = "静默"
    case thinking = "思考"
    case executing = "执行"
    case learning = "学习"
    case awaitingApproval = "等待审批"
    
    var color: Color {
        switch self {
        case .silent: Color(hex: "D4D9D6")
        case .thinking: Color(hex: "B8C9D4")
        case .executing: Color(hex: "A8C4B8")
        case .learning: Color(hex: "C8B8D4")
        case .awaitingApproval: Color(hex: "E0C8B0")
        }
    }
    
    var animation: LivingAnimation {
        switch self {
        case .silent: .still
        case .thinking: .slowPulse(period: 3.0)
        case .executing: .flowing(period: 2.5)
        case .learning: .ripple(period: 1.8)
        case .awaitingApproval: .gentleBounce(period: 2.0)
        }
    }
    
    var audioReactive: Bool {
        switch self {
        case .executing, .learning: true
        default: false
        }
    }
}

enum LivingAnimation: Equatable {
    case still
    case slowPulse(period: Double)
    case flowing(period: Double)
    case ripple(period: Double)
    case gentleBounce(period: Double)
}

// ── Life Skin ──
enum LifeSkin: String, CaseIterable, Codable {
    case morningMist = "晨雾"
    case tide = "潮汐"
    case forestBreath = "林息"
    case sunsetGlow = "霞光"
    
    var primary: Color {
        switch self {
        case .morningMist: Color(hex: "C4D7D1")
        case .tide: Color(hex: "8BB8C9")
        case .forestBreath: Color(hex: "A3C4A3")
        case .sunsetGlow: Color(hex: "E8C4A0")
        }
    }
    
    var secondary: Color {
        switch self {
        case .morningMist: Color(hex: "DCE8E2")
        case .tide: Color(hex: "B8D4E0")
        case .forestBreath: Color(hex: "C8DCC8")
        case .sunsetGlow: Color(hex: "F0DCC8")
        }
    }
    
    var breathPeriod: Double {
        switch self {
        case .morningMist: 4.0
        case .tide: 6.0
        case .forestBreath: 5.0
        case .sunsetGlow: 4.5
        }
    }
}

// ── Color Helper ──
extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let r = Double((int >> 16) & 0xFF) / 255.0
        let g = Double((int >> 8) & 0xFF) / 255.0
        let b = Double(int & 0xFF) / 255.0
        self.init(red: r, green: g, blue: b)
    }
}

// ── Audio Config ──
struct AudioConfig {
    static let microphoneDefaultOff = true
    static let audioNeverUploaded = true
    static let audioNeverSaved = true
    static let fftLocalOnly = true
}
