import SwiftUI
import Foundation

// MARK: - NEXARA macOS App Entry Point
// Auto-starts the local Runtime (8770) on launch. No terminal required.

@main
struct NEXARALivingApp: App {
    var body: some Scene {
        WindowGroup {
            BrainView()
                .preferredColorScheme(.light)
        }
        .windowStyle(.hiddenTitleBar)
        .windowResizability(.contentMinSize)
        .defaultSize(width: 1200, height: 800)
    }
}
