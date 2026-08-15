import SwiftUI
import Foundation
import AppKit

// MARK: - NEXARA macOS App Entry Point
// Auto-starts the local Runtime on launch (port: RuntimeConfiguration.port, 8765). No terminal required.

@main
struct NEXARALivingApp: App {
    init() {
        // TODO(branding, PHASE 11): 「门+金点」品牌图标待资产管线替换 —
        // nexara_sovereign_core.png 为占位资产（引用位置：macOSApp.swift / AppIconCatalog.swift / project.pbxproj Resources）。
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
