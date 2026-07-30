import SwiftUI

// MARK: - NEXARA Living Interface Design Token System
// Direction A: Warm Ivory + Champagne Gold

enum NXColor {
    // Warm Palette
    static let ivory = Color(hex: "ECE4D8")
    static let ivoryLight = Color(hex: "F5F0EB")
    static let graphite = Color(hex: "3C3C3C")
    static let graphiteSoft = Color(hex: "6B6B6B")
    static let champagne = Color(hex: "D4AF37")
    static let moss = Color(hex: "8B9A6E")
    static let amber = Color(hex: "D4894E")
    static let rose = Color(hex: "C46A6A")

    // Functional
    static let success = Color.green
    static let warning = Color.orange
    static let error = Color.red
    static let info = Color.blue
}

enum NXSpacing {
    static let xs: CGFloat = 4
    static let sm: CGFloat = 8
    static let md: CGFloat = 12
    static let lg: CGFloat = 16
    static let xl: CGFloat = 24
    static let xxl: CGFloat = 32
    static let xxxl: CGFloat = 48
}

enum NXRadius {
    static let sm: CGFloat = 6
    static let md: CGFloat = 10
    static let lg: CGFloat = 16
    static let xl: CGFloat = 24
    static let pill: CGFloat = .infinity
}

enum NXFont {
    static let display = Font.largeTitle.bold()
    static let heading = Font.title.weight(.semibold)
    static let subheading = Font.title2.weight(.medium)
    static let body = Font.body
    static let caption = Font.caption
    static let code = Font.system(.caption, design: .monospaced)
}

enum NXDuration {
    static let micro: Double = 0.15
    static let fast: Double = 0.25
    static let normal: Double = 0.35
    static let slow: Double = 0.5
    static let breathe: Double = 4.0
}

extension Color {
    init(hex: String) {
        let scanner = Scanner(string: hex)
        var rgb: UInt64 = 0
        scanner.scanHexInt64(&rgb)
        self.init(
            red: Double((rgb >> 16) & 0xFF) / 255.0,
            green: Double((rgb >> 8) & 0xFF) / 255.0,
            blue: Double(rgb & 0xFF) / 255.0
        )
    }
}
