import SwiftUI

// ── NEXARA Living Interface shared entry point ──
// This file is NO LONGER the @main entry. 
// The macOS entry is macOS/macOSApp.swift which uses ContentView.
// Kept as a shared module component for future iOS entry point.

struct LivingInterfaceEntry: View {
    var body: some View {
        ContentView()
            .preferredColorScheme(.light)
    }
}
