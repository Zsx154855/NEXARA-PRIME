import SwiftUI

// ── Living Models: Types, Enums, Extensions ──

// MARK: - Living State
enum LivingState: String, CaseIterable, Codable {
    case silent = "静默"
    case thinking = "思考"
    case planning = "规划"
    case executing = "执行"
    case learning = "学习"
    case awaitingApproval = "等待审批"
    case recovery = "恢复"

    var label: String { rawValue }

    var color: Color {
        switch self {
        case .silent: Color(hex: "D8D2CA")
        case .thinking: Color(hex: "C49A55")
        case .planning: Color(hex: "D58F98")
        case .executing: Color(hex: "72865D")
        case .learning: Color(hex: "B8A890")
        case .awaitingApproval: Color(hex: "D58F98")
        case .recovery: Color(hex: "C49A55")
        }
    }

    var icon: String {
        switch self {
        case .silent: "moon.zzz.fill"
        case .thinking: "brain.head.profile"
        case .planning: "map.fill"
        case .executing: "gearshape.2.fill"
        case .learning: "lightbulb.fill"
        case .awaitingApproval: "hand.raised.fill"
        case .recovery: "arrow.triangle.2.circlepath"
        }
    }
}

// MARK: - Life Skin
enum LifeSkin: String, CaseIterable, Codable {
    case morningMist = "晨雾"
    case tide = "潮汐"
    case forestBreath = "林息"
    case sunsetGlow = "霞光"
    case galaxy = "星云"

    var primary: Color {
        switch self {
        case .morningMist: Color(hex: "D8D2CA")
        case .tide: Color(hex: "C49A55")
        case .forestBreath: Color(hex: "72865D")
        case .sunsetGlow: Color(hex: "D58F98")
        case .galaxy: Color(hex: "0969DA")
        }
    }

    var secondary: Color {
        switch self {
        case .morningMist: Color(hex: "ECE8E2")
        case .tide: Color(hex: "D8C8A0")
        case .forestBreath: Color(hex: "A8B898")
        case .sunsetGlow: Color(hex: "E8C8C8")
        case .galaxy: Color(hex: "D0D7DE")
        }
    }
}

// MARK: - Color Helper
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

// MARK: - Audio Config
struct AudioConfig {
    static let microphoneDefaultOff = true
    static let audioNeverUploaded = true
    static let audioNeverSaved = true
    static let fftLocalOnly = true
}

// MARK: ── NEXARA V2 Canonical UI Token System: Warm Ivory ──
// PRIMARY: Warm Ivory #F5F0E8 (65%)
// SECONDARY: Mist Gray #D8D2CA (20%)
// LIFE: Dust Rose #D58F98 (8%)
// IDENTITY: Champagne Gold #C49A55 (5%)
// HEALTH: Moss Green #72865D (2%)

enum NXSpacing {
    static let xs: CGFloat = 4
    static let sm: CGFloat = 8
    static let md: CGFloat = 12
    static let lg: CGFloat = 16
    static let xl: CGFloat = 20
    static let xxl: CGFloat = 24
    static let xxxl: CGFloat = 32
    static let pageHorizontal: CGFloat = 20
    static let moduleGap: CGFloat = 20
    static let moduleInternal: CGFloat = 12
    static let sectionGap: CGFloat = 32
}

enum NXRadius {
    static let chip: CGFloat = 20
    static let control: CGFloat = 14
    static let card: CGFloat = 24
    static let majorSurface: CGFloat = 28
    static let composer: CGFloat = 22
    static let tabBar: CGFloat = 28
}

enum NXTypography {
    static let pageTitleFont: Font = .title2.weight(.semibold)
    static let sectionTitleFont: Font = .headline.weight(.regular)
    static let bodyFont: Font = .body
    static let secondaryFont: Font = .subheadline
    static let labelFont: Font = .footnote
    static let captionFont: Font = .caption
    static let navigationLabelFont: Font = .caption2

    static func pageTitle(_ content: String) -> Text { Text(content).font(.title2).fontWeight(.semibold) }
    static func sectionTitle(_ content: String) -> Text { Text(content).font(.headline).fontWeight(.regular) }
    static func body(_ content: String) -> Text { Text(content).font(.body) }
    static func secondary(_ content: String) -> Text { Text(content).font(.subheadline) }
    static func label(_ content: String) -> Text { Text(content).font(.footnote) }
    static func caption(_ content: String) -> Text { Text(content).font(.caption) }
}

enum NXColor {
    // ── V2 Warm Ivory Palette (Light Mode) ──
    // Canonical base: warmIvory #F5F0E8 — the single source of truth.
    static let warmIvory = Color(hex: "F5F0E8")
    static let warmIvoryDark = Color(hex: "ECE4D8")
    static let mistGray = Color(hex: "D8D2CA")
    static let mistGrayLight = Color(hex: "E8E4DE")
    static let graphite = Color(hex: "302F2D")
    static let graphiteSecondary = Color(hex: "6B6560")
    static let graphiteTertiary = Color(hex: "9B9590")
    static let dustRose = Color(hex: "D58F98")
    static let dustRoseLight = Color(hex: "E8B8BE")
    static let champagneGold = Color(hex: "C49A55")
    static let champagneGoldLight = Color(hex: "D8B878")
    static let mossGreen = Color(hex: "72865D")
    static let mossGreenLight = Color(hex: "95A885")

    // ── Page Atmosphere Gradient Stops ──
    // Visible "light-from-above" radial depth.
    // atmoCenter creates a concentrated warm light pool at page top;
    // atmoEdge provides a perceptible shadowed depth at page bottom.
    static let atmoCenter = Color(hex: "FFFCF5")   // bright warm glow — light pool
    static let atmoEdge   = Color(hex: "E8DFD0")   // shadowed edge — visible depth

    // ── Section Surface Tints (ΔE 8–12 from warmIvory) ──
    // Each NXSection applies a clearly perceptible hue shift.
    // Visible as distinct "atmosphere" when switching between sections.
    // PHASE 11 (V1.1): 六区 IA — 新增 memorySurface 供 MEMORY 区独立氛围。
    static let coreSurface     = Color(hex: "FDF6E4")  // HOME — champagne warmth — gold undertone
    static let identitySurface = Color(hex: "FDF2ED")  // CONVERSATION — soft rose — pink undertone
    static let missionSurface  = Color(hex: "EDF2E7")  // MISSIONS — sage clarity — green-gray undertone
    static let toolsSurface    = Color(hex: "F1EEF3")  // TRUST — lavender precision — violet undertone
    static let memorySurface   = Color(hex: "F0EAE0")  // MEMORY — warm parchment — contemplative
    static let systemSurface   = Color(hex: "E7E2D6")  // SETTINGS — stone calm — deeper muted tone

    // ── Sidebar ──
    static let sidebarBase = Color(hex: "EDE8E0")    // slightly recessed from page

    // ── Glass Surface ──
    static let glassBorder = Color.white.opacity(0.35)
    static let glassTint = Color.white.opacity(0.18)
    static let glassHighlight = Color.white.opacity(0.65)
    static let glassShadow = Color.black.opacity(0.04)
    static let surfaceElevated = Color.white.opacity(0.75)
    static let surfaceBase = Color.white.opacity(0.55)

    // ── Status ──
    static let approveGreen = Color(hex: "6BA87A")
    static let rejectRed = Color(hex: "D48888")
    static let pauseAmber = Color(hex: "E0C8B0")

    // ── Dark Mode Palette ──
    // All dark colors preserve warmIvory's hue (40°) at deep luminance.
    // The warm undertone prevents the sterile "pure black" feel.
    static let darkBase      = Color(hex: "26231E")  // page background — warm charcoal
    static let darkSurface   = Color(hex: "2D2A24")  // cards / elevated surfaces
    static let darkElevated  = Color(hex: "33302A")  // prominent cards / modals
    static let darkSidebar   = Color(hex: "1F1D19")  // recessed sidebar — deepest
    static let darkText       = Color(hex: "E8E4DE")  // primary text — warm off-white
    static let darkTextSecondary = Color(hex: "A8A29C")  // secondary text
    static let darkTextTertiary = Color(hex: "78726C")   // tertiary / captions
    static let darkBorder     = Color.white.opacity(0.08)  // subtle separators
    static let darkShadow     = Color.black.opacity(0.3)   // deeper shadow for dark
    static let darkChampagne  = Color(hex: "D4B06A")  // brighter gold — visible on dark
    static let darkDustRose   = Color(hex: "E0A5AC")  // lighter rose
    static let darkMossGreen  = Color(hex: "8DA878")  // lighter green
}

// MARK: - NEXARA Glass Enhancement Tokens
// Minimal gradient tokens used exclusively by glassCard() for edge-light effect.
// Page backgrounds use solid NXColor.warmIvory — no gradient system needed.

enum NXGradient {
    // ── Glass Surface Enhancement ──
    static let glassEdgeLight = Color.white.opacity(0.25)
    static let glassEdgeFade  = Color.white.opacity(0.04)
}

enum NXMotion {
    static let pulseDuration: Double = 4.0
    static let orbitDurationSlow: Double = 18.0
    static let orbitDurationFast: Double = 10.0
    static let transitionDefault: Double = 0.35
    static let interactionSpring = Animation.spring(response: 0.35, dampingFraction: 0.75)
    static func breathPeriod(for skin: LifeSkin) -> Double {
        switch skin {
        case .morningMist: return 4.0
        case .tide: return 6.0
        case .forestBreath: return 5.0
        case .sunsetGlow: return 4.5
        case .galaxy: return 5.0
        }
    }
}

enum NXIcon {
    static let renderingMode: SymbolRenderingMode = .hierarchical
    static let tabToday = "sun.max.fill"
    static let tabMemory = "brain.head.profile"
    static let tabLearning = "lightbulb.fill"
    static let tabApproval = "hand.raised.fill"
    static let tabStatus = "circle.hexagongrid.fill"
    static let send = "arrow.up.circle.fill"
    static let micOn = "mic.fill"
    static let micOff = "mic.slash.fill"
    static let approve = "checkmark.circle.fill"
    static let reject = "xmark.circle.fill"
    static let pause = "pause.circle.fill"
    static let sparkle = "sparkle"
    static let person = "person.crop.circle.badge.checkmark"
}

enum NXHitTarget {
    static let minimum: CGFloat = 44
}
