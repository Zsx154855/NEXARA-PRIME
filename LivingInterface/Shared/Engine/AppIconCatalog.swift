import Foundation

// ── App Icon Catalog: single source of truth for all 24 icons ──
struct AppIconCatalog {
    static let allIcons: [AppIconOption] = [
        // ── Board B: 6 icons ──
        AppIconOption(
            id: "b01_liquid_life_core", displayName: "液态生命核心", family: .lifeCore,
            assetName: "b01_liquid_life_core", alternateIconName: "b01_liquid_life_core",
            previewAssetName: "b01_liquid_life_core_preview",
            platformAvailability: .init(macOS: true, iOS: true),
            isPrimary: true, sourceBoard: "B", sourceIndex: 1,
            accessibilityLabel: "默认应用图标：液态生命核心", tone: "warmSage", sortOrder: 1
        ),
        AppIconOption(
            id: "b02_spatial_brain", displayName: "空间化主脑", family: .spatialBrain,
            assetName: "b02_spatial_brain", alternateIconName: "b02_spatial_brain",
            previewAssetName: "b02_spatial_brain_preview",
            platformAvailability: .init(macOS: true, iOS: true),
            isPrimary: false, sourceBoard: "B", sourceIndex: 2,
            accessibilityLabel: "应用图标：空间化主脑", tone: "forestGreen", sortOrder: 2
        ),
        AppIconOption(
            id: "b03_music_resonance", displayName: "音乐共振", family: .musicResonance,
            assetName: "b03_music_resonance", alternateIconName: "b03_music_resonance",
            previewAssetName: "b03_music_resonance_preview",
            platformAvailability: .init(macOS: true, iOS: true),
            isPrimary: false, sourceBoard: "B", sourceIndex: 3,
            accessibilityLabel: "应用图标：音乐共振", tone: "oceanBlue", sortOrder: 3
        ),
        AppIconOption(
            id: "b04_liquid_life_core_deep", displayName: "液态生命核心·深空", family: .lifeCore,
            assetName: "b04_liquid_life_core_deep", alternateIconName: "b04_liquid_life_core_deep",
            previewAssetName: "b04_liquid_life_core_deep_preview",
            platformAvailability: .init(macOS: true, iOS: true),
            isPrimary: false, sourceBoard: "B", sourceIndex: 4,
            accessibilityLabel: "应用图标：液态生命核心深空变体", tone: "deepOcean", sortOrder: 4
        ),
        AppIconOption(
            id: "b05_spatial_brain_panorama", displayName: "空间化主脑·全景", family: .spatialBrain,
            assetName: "b05_spatial_brain_panorama", alternateIconName: "b05_spatial_brain_panorama",
            previewAssetName: "b05_spatial_brain_panorama_preview",
            platformAvailability: .init(macOS: true, iOS: true),
            isPrimary: false, sourceBoard: "B", sourceIndex: 5,
            accessibilityLabel: "应用图标：空间化主脑全景", tone: "skyBlue", sortOrder: 5
        ),
        AppIconOption(
            id: "b06_music_resonance_spectrum", displayName: "音乐共振·光谱", family: .musicResonance,
            assetName: "b06_music_resonance_spectrum", alternateIconName: "b06_music_resonance_spectrum",
            previewAssetName: "b06_music_resonance_spectrum_preview",
            platformAvailability: .init(macOS: true, iOS: true),
            isPrimary: false, sourceBoard: "B", sourceIndex: 6,
            accessibilityLabel: "应用图标：音乐共振光谱", tone: "pastelRainbow", sortOrder: 6
        ),

        // ── Board C: 6 icons ──
        AppIconOption(
            id: "c01_morning_mist_soft", displayName: "晨雾之息·柔光", family: .nature,
            assetName: "c01_morning_mist_soft", alternateIconName: "c01_morning_mist_soft",
            previewAssetName: "c01_morning_mist_soft_preview",
            platformAvailability: .init(macOS: true, iOS: true),
            isPrimary: false, sourceBoard: "C", sourceIndex: 1,
            accessibilityLabel: "应用图标：晨雾之息柔光", tone: "morningMist", sortOrder: 7
        ),
        AppIconOption(
            id: "c02_tidal_resonance_deep", displayName: "潮汐共振·深海", family: .musicResonance,
            assetName: "c02_tidal_resonance_deep", alternateIconName: "c02_tidal_resonance_deep",
            previewAssetName: "c02_tidal_resonance_deep_preview",
            platformAvailability: .init(macOS: true, iOS: true),
            isPrimary: false, sourceBoard: "C", sourceIndex: 2,
            accessibilityLabel: "应用图标：潮汐共振深海", tone: "deepTide", sortOrder: 8
        ),
        AppIconOption(
            id: "c03_forest_heart", displayName: "林息之心", family: .nature,
            assetName: "c03_forest_heart", alternateIconName: "c03_forest_heart",
            previewAssetName: "c03_forest_heart_preview",
            platformAvailability: .init(macOS: true, iOS: true),
            isPrimary: false, sourceBoard: "C", sourceIndex: 3,
            accessibilityLabel: "应用图标：林息之心", tone: "forestHeart", sortOrder: 9
        ),
        AppIconOption(
            id: "c04_morning_mist_clear", displayName: "晨雾之息·通透", family: .nature,
            assetName: "c04_morning_mist_clear", alternateIconName: "c04_morning_mist_clear",
            previewAssetName: "c04_morning_mist_clear_preview",
            platformAvailability: .init(macOS: true, iOS: true),
            isPrimary: false, sourceBoard: "C", sourceIndex: 4,
            accessibilityLabel: "应用图标：晨雾之息通透", tone: "clearMist", sortOrder: 10
        ),
        AppIconOption(
            id: "c05_tidal_resonance_light", displayName: "潮汐共振·浅海", family: .musicResonance,
            assetName: "c05_tidal_resonance_light", alternateIconName: "c05_tidal_resonance_light",
            previewAssetName: "c05_tidal_resonance_light_preview",
            platformAvailability: .init(macOS: true, iOS: true),
            isPrimary: false, sourceBoard: "C", sourceIndex: 5,
            accessibilityLabel: "应用图标：潮汐共振浅海", tone: "shallowTide", sortOrder: 11
        ),
        AppIconOption(
            id: "c06_sunset_realm", displayName: "霞光之境", family: .nature,
            assetName: "c06_sunset_realm", alternateIconName: "c06_sunset_realm",
            previewAssetName: "c06_sunset_realm_preview",
            platformAvailability: .init(macOS: true, iOS: true),
            isPrimary: false, sourceBoard: "C", sourceIndex: 6,
            accessibilityLabel: "应用图标：霞光之境", tone: "sunsetGlow", sortOrder: 12
        ),

        // ── Board D: 12 icons ──
        AppIconOption(
            id: "d01_product_liquid", displayName: "智慧液态", family: .productDesign,
            assetName: "d01_product_liquid", alternateIconName: "d01_product_liquid",
            previewAssetName: "d01_product_liquid_preview",
            platformAvailability: .init(macOS: true, iOS: true),
            isPrimary: false, sourceBoard: "D", sourceIndex: 1,
            accessibilityLabel: "应用图标：智慧液态", tone: "smartLiquid", sortOrder: 13
        ),
        AppIconOption(
            id: "d02_product_forest", displayName: "林息液态", family: .productDesign,
            assetName: "d02_product_forest", alternateIconName: "d02_product_forest",
            previewAssetName: "d02_product_forest_preview",
            platformAvailability: .init(macOS: true, iOS: true),
            isPrimary: false, sourceBoard: "D", sourceIndex: 2,
            accessibilityLabel: "应用图标：林息液态", tone: "forestLiquid", sortOrder: 14
        ),
        AppIconOption(
            id: "d03_product_sunset", displayName: "霞光液态", family: .productDesign,
            assetName: "d03_product_sunset", alternateIconName: "d03_product_sunset",
            previewAssetName: "d03_product_sunset_preview",
            platformAvailability: .init(macOS: true, iOS: true),
            isPrimary: false, sourceBoard: "D", sourceIndex: 3,
            accessibilityLabel: "应用图标：霞光液态", tone: "sunsetLiquid", sortOrder: 15
        ),
        AppIconOption(
            id: "d04_documents_crystal", displayName: "晶层文档", family: .documents,
            assetName: "d04_documents_crystal", alternateIconName: "d04_documents_crystal",
            previewAssetName: "d04_documents_crystal_preview",
            platformAvailability: .init(macOS: true, iOS: true),
            isPrimary: false, sourceBoard: "D", sourceIndex: 4,
            accessibilityLabel: "应用图标：晶层文档", tone: "crystalSheets", sortOrder: 16
        ),
        AppIconOption(
            id: "d05_documents_tidal", displayName: "潮汐档案", family: .documents,
            assetName: "d05_documents_tidal", alternateIconName: "d05_documents_tidal",
            previewAssetName: "d05_documents_tidal_preview",
            platformAvailability: .init(macOS: true, iOS: true),
            isPrimary: false, sourceBoard: "D", sourceIndex: 5,
            accessibilityLabel: "应用图标：潮汐档案", tone: "tidalDocs", sortOrder: 17
        ),
        AppIconOption(
            id: "d06_documents_amber", displayName: "琥珀知识库", family: .documents,
            assetName: "d06_documents_amber", alternateIconName: "d06_documents_amber",
            previewAssetName: "d06_documents_amber_preview",
            platformAvailability: .init(macOS: true, iOS: true),
            isPrimary: false, sourceBoard: "D", sourceIndex: 6,
            accessibilityLabel: "应用图标：琥珀知识库", tone: "amberKnowledge", sortOrder: 18
        ),
        AppIconOption(
            id: "d07_core_prism", displayName: "棱镜生命核心", family: .lifeCore,
            assetName: "d07_core_prism", alternateIconName: "d07_core_prism",
            previewAssetName: "d07_core_prism_preview",
            platformAvailability: .init(macOS: true, iOS: true),
            isPrimary: false, sourceBoard: "D", sourceIndex: 7,
            accessibilityLabel: "应用图标：棱镜生命核心", tone: "prismViolet", sortOrder: 19
        ),
        AppIconOption(
            id: "d08_core_moss", displayName: "苔绿生命核心", family: .lifeCore,
            assetName: "d08_core_moss", alternateIconName: "d08_core_moss",
            previewAssetName: "d08_core_moss_preview",
            platformAvailability: .init(macOS: true, iOS: true),
            isPrimary: false, sourceBoard: "D", sourceIndex: 8,
            accessibilityLabel: "应用图标：苔绿生命核心", tone: "mossGreen", sortOrder: 20
        ),
        AppIconOption(
            id: "d09_core_amber", displayName: "琥珀生命核心", family: .lifeCore,
            assetName: "d09_core_amber", alternateIconName: "d09_core_amber",
            previewAssetName: "d09_core_amber_preview",
            platformAvailability: .init(macOS: true, iOS: true),
            isPrimary: false, sourceBoard: "D", sourceIndex: 9,
            accessibilityLabel: "应用图标：琥珀生命核心", tone: "amberCore", sortOrder: 21
        ),
        AppIconOption(
            id: "d10_spatial_violet", displayName: "紫晶空间主脑", family: .spatialBrain,
            assetName: "d10_spatial_violet", alternateIconName: "d10_spatial_violet",
            previewAssetName: "d10_spatial_violet_preview",
            platformAvailability: .init(macOS: true, iOS: true),
            isPrimary: false, sourceBoard: "D", sourceIndex: 10,
            accessibilityLabel: "应用图标：紫晶空间主脑", tone: "violetSpatial", sortOrder: 22
        ),
        AppIconOption(
            id: "d11_spatial_tidal", displayName: "潮汐空间主脑", family: .spatialBrain,
            assetName: "d11_spatial_tidal", alternateIconName: "d11_spatial_tidal",
            previewAssetName: "d11_spatial_tidal_preview",
            platformAvailability: .init(macOS: true, iOS: true),
            isPrimary: false, sourceBoard: "D", sourceIndex: 11,
            accessibilityLabel: "应用图标：潮汐空间主脑", tone: "tidalSpatial", sortOrder: 23
        ),
        AppIconOption(
            id: "d12_spatial_sunset", displayName: "霞光空间主脑", family: .spatialBrain,
            assetName: "d12_spatial_sunset", alternateIconName: "d12_spatial_sunset",
            previewAssetName: "d12_spatial_sunset_preview",
            platformAvailability: .init(macOS: true, iOS: true),
            isPrimary: false, sourceBoard: "D", sourceIndex: 12,
            accessibilityLabel: "应用图标：霞光空间主脑", tone: "sunsetSpatial", sortOrder: 24
        ),
    ]

    // ── Queries ──
    static var primaryIcon: AppIconOption {
        allIcons.first(where: \.isPrimary)!
    }

    static var iconCount: Int { allIcons.count }

    static func icon(by id: String) -> AppIconOption? {
        allIcons.first { $0.id == id }
    }

    static func icons(for family: AppIconFamily) -> [AppIconOption] {
        allIcons.filter { $0.family == family }.sorted { $0.sortOrder < $1.sortOrder }
    }

    static var allIDs: [String] { allIcons.map(\.id) }
    static var allAssetNames: [String] { allIcons.map(\.assetName) }

    func validate() -> [String] {
        var errors: [String] = []
        let ids = Self.allIcons.map(\.id)
        let idSet = Set(ids)
        if idSet.count != ids.count { errors.append("DUPLICATE_IDS") }
        if Self.allIcons.filter(\.isPrimary).count != 1 { errors.append("MULTIPLE_OR_ZERO_PRIMARY") }
        if Self.allIcons.count != 24 { errors.append("ICON_COUNT_NOT_24") }
        let forbidden = ["a01", "a02", "a03"]
        for fid in forbidden {
            if ids.contains(where: { $0.hasPrefix(fid) }) { errors.append("FORBIDDEN_FIRST_BOARD_ID: \(fid)") }
        }
        let assetNames = Set(Self.allIcons.map(\.assetName))
        if assetNames.count != Self.allIcons.count { errors.append("DUPLICATE_ASSET_NAMES") }
        for icon in Self.allIcons {
            if icon.displayName.isEmpty { errors.append("MISSING_DISPLAY_NAME: \(icon.id)") }
            if icon.accessibilityLabel.isEmpty { errors.append("MISSING_ACCESSIBILITY_LABEL: \(icon.id)") }
        }
        let sortOrders = Set(Self.allIcons.map(\.sortOrder))
        if sortOrders.count != Self.allIcons.count { errors.append("DUPLICATE_SORT_ORDER") }
        return errors
    }
}
