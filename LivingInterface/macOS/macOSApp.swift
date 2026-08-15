import SwiftUI
import Foundation
import AppKit

// MARK: - NEXARA macOS App Entry Point
// Auto-starts the local Runtime on launch (port: RuntimeConfiguration.port, 8765). No terminal required.

@main
struct NEXARALivingApp: App {
    init() {
        // 主图标已替换为「门+金点」（ADR-UI-001）；旧占位保留为 nexara_sovereign_core_legacy.png。
        // Set the 柏韩·主权核心 app icon for Dock, App Switcher, and Finder.
        if let icon = NSImage(named: "nexara_sovereign_core") {
            NSApplication.shared.applicationIconImage = icon
        }
    }

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
