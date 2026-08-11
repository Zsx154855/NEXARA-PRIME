import SwiftUI
import Combine

/// Persists user icon selection via @AppStorage.
/// Fallback to default on invalid/missing ID or resource.
@MainActor
final class AppIconSelectionStore: ObservableObject {
    @AppStorage(AppIconStorageKey.selectedIconID) var storedIconID: String = ""

    @Published var selectedIcon: AppIconOption
    @Published var isApplying: Bool = false
    @Published var lastError: String?

    init() {
        let resolved = Self.resolveIcon(id: Self.resolveStoredID())
        selectedIcon = resolved
    }

    private static func resolveStoredID() -> String {
        // Trigger @AppStorage read
        let raw = UserDefaults.standard.string(forKey: AppIconStorageKey.selectedIconID) ?? ""
        return raw.isEmpty ? AppIconCatalog.primaryIcon.id : raw
    }

    private static func resolveIcon(id: String) -> AppIconOption {
        AppIconCatalog.icon(by: id) ?? AppIconCatalog.primaryIcon
    }

    func selectIcon(_ icon: AppIconOption) {
        selectedIcon = icon
    }

    func applyIcon(_ icon: AppIconOption) {
        isApplying = true
        lastError = nil

        #if os(iOS)
        guard UIApplication.shared.supportsAlternateIcons else {
            lastError = "当前设备不支持切换应用图标"
            isApplying = false
            return
        }
        let name: String? = icon.isPrimary ? nil : icon.alternateIconName
        UIApplication.shared.setAlternateIconName(name) { [weak self] error in
            Task { @MainActor in
                self?.isApplying = false
                if let error {
                    self?.lastError = "图标切换失败：\(error.localizedDescription)"
                } else {
                    self?.commitSelection(icon)
                }
            }
        }
        #elseif os(macOS)
        // macOS: update Dock icon
        if icon.isPrimary {
            NSApplication.shared.applicationIconImage = nil
        } else {
            if let img = NSImage(named: icon.assetName) {
                NSApplication.shared.applicationIconImage = img
            } else {
                lastError = "图标资源缺失：\(icon.assetName)"
                isApplying = false
                return
            }
        }
        commitSelection(icon)
        isApplying = false
        #endif
    }

    func restoreDefault() {
        let primary = AppIconCatalog.primaryIcon
        #if os(iOS)
        if UIApplication.shared.supportsAlternateIcons {
            UIApplication.shared.setAlternateIconName(nil) { [weak self] _ in
                Task { @MainActor in
                    self?.commitSelection(primary)
                }
            }
        } else {
            commitSelection(primary)
        }
        #elseif os(macOS)
        NSApplication.shared.applicationIconImage = nil
        commitSelection(primary)
        #endif
    }

    private func commitSelection(_ icon: AppIconOption) {
        storedIconID = icon.id
        selectedIcon = icon
        lastError = nil
    }

    func validateResourceExists(for icon: AppIconOption) -> Bool {
        #if os(macOS)
        return NSImage(named: icon.assetName) != nil
        #else
        return UIImage(named: icon.assetName) != nil
        #endif
    }
}
