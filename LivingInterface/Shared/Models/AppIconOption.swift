import Foundation

// ── App Icon Family ──
enum AppIconFamily: String, CaseIterable, Codable, Identifiable {
    case lifeCore = "lifeCore"
    case spatialBrain = "spatialBrain"
    case musicResonance = "musicResonance"
    case nature = "nature"
    case productDesign = "productDesign"
    case documents = "documents"

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .lifeCore: "生命核心"
        case .spatialBrain: "空间主脑"
        case .musicResonance: "音乐共振"
        case .nature: "自然之境"
        case .productDesign: "产品设计"
        case .documents: "文档系列"
        }
    }

    var sortOrder: Int {
        switch self {
        case .lifeCore: 0
        case .spatialBrain: 1
        case .musicResonance: 2
        case .nature: 3
        case .productDesign: 4
        case .documents: 5
        }
    }
}

// ── App Icon Option ──
struct AppIconOption: Identifiable, Codable, Equatable {
    let id: String
    let displayName: String
    let family: AppIconFamily
    let assetName: String
    let alternateIconName: String?
    let previewAssetName: String
    let platformAvailability: PlatformAvailability
    let isPrimary: Bool
    let sourceBoard: String
    let sourceIndex: Int
    let accessibilityLabel: String
    let tone: String
    let sortOrder: Int

    struct PlatformAvailability: Codable, Equatable {
        let macOS: Bool
        let iOS: Bool
    }

    static func == (lhs: AppIconOption, rhs: AppIconOption) -> Bool { lhs.id == rhs.id }
}

// ── Pinned storage key ──
enum AppIconStorageKey {
    static let selectedIconID = "nexara.selectedAppIconID"
}
