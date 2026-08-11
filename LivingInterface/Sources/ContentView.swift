import SwiftUI

// ── ContentView (iOS / shared target) ──
// On macOS, the actual entry point is macOS/BrainView.swift.
// This file is compiled for both targets, so we keep it minimal to avoid
// redeclaring types already defined in BrainView.swift.

// NOTE: All page types (NXPage, NXSection, NXRuntime) and views are defined
// in macOS/BrainView.swift. Do NOT redefine them here.

/// Shared fallback view for non-macOS targets.
struct ContentView: View {
    @StateObject private var engine = LivingEngine()
    @State private var runtime = NXRuntime()
    
    var body: some View {
        BrainView()
    }
}

#Preview {
    ContentView()
}
