import XCTest

@MainActor final class AppIconCatalogTests: XCTestCase {

    // Test 1: Icon count = 24
    func test_iconCountIs24() {
        XCTAssertEqual(AppIconCatalog.iconCount, 24)
        XCTAssertEqual(AppIconCatalog.allIcons.count, 24)
    }

    // Test 2: All IDs unique
    func test_allIDsUnique() {
        let ids = AppIconCatalog.allIcons.map(\.id)
        XCTAssertEqual(Set(ids).count, ids.count)
    }

    // Test 3: Exactly one primary icon
    func test_exactlyOnePrimaryIcon() {
        let primaries = AppIconCatalog.allIcons.filter(\.isPrimary)
        XCTAssertEqual(primaries.count, 1)
        XCTAssertEqual(primaries.first?.id, "b01_liquid_life_core")
    }

    // Test 4: No first board IDs
    func test_noFirstBoardIcons() {
        let ids = AppIconCatalog.allIcons.map(\.id)
        for id in ids {
            XCTAssertFalse(id.hasPrefix("a01") || id.hasPrefix("a02") || id.hasPrefix("a03"),
                          "Forbidden first board ID found: \(id)")
        }
    }

    // Test 5: Every icon has display name
    func test_allIconsHaveDisplayName() {
        for icon in AppIconCatalog.allIcons {
            XCTAssertFalse(icon.displayName.isEmpty, "Icon \(icon.id) missing displayName")
        }
    }

    // Test 6: Every icon has accessibility label
    func test_allIconsHaveAccessibilityLabel() {
        for icon in AppIconCatalog.allIcons {
            XCTAssertFalse(icon.accessibilityLabel.isEmpty, "Icon \(icon.id) missing accessibilityLabel")
        }
    }

    // Test 7: All asset names unique
    func test_allAssetNamesUnique() {
        let names = AppIconCatalog.allIcons.map(\.assetName)
        XCTAssertEqual(Set(names).count, names.count)
    }

    // Test 8: All sort orders unique
    func test_allSortOrdersUnique() {
        let orders = AppIconCatalog.allIcons.map(\.sortOrder)
        XCTAssertEqual(Set(orders).count, orders.count)
    }

    // Test 9: Invalid ID returns nil
    func test_invalidIDReturnsNil() {
        XCTAssertNil(AppIconCatalog.icon(by: "nonexistent_id"))
    }

    // Test 10: Primary icon retrievable
    func test_primaryIconRetrievable() {
        XCTAssertEqual(AppIconCatalog.primaryIcon.id, "b01_liquid_life_core")
    }

    // Test 11: validate() returns zero errors for correct catalog
    func test_validateReturnsZeroErrors() {
        let errors = AppIconCatalog().validate()
        XCTAssertEqual(errors.count, 0, "Validation errors: \(errors.joined(separator: ", "))")
    }

    // Test 12: All icons belong to valid families
    func test_allIconsHaveValidFamily() {
        let validFamilies = Set(AppIconFamily.allCases.map(\.rawValue))
        for icon in AppIconCatalog.allIcons {
            XCTAssertTrue(validFamilies.contains(icon.family.rawValue),
                         "Icon \(icon.id) has invalid family: \(icon.family.rawValue)")
        }
    }

    // Test 13: Primary icon is in lifeCore family
    func test_primaryIconIsLifeCore() {
        XCTAssertEqual(AppIconCatalog.primaryIcon.family, .lifeCore)
    }

    // Test 14: Filter by family returns correct subset
    func test_familyFilter() {
        let lifeCoreIcons = AppIconCatalog.icons(for: .lifeCore)
        XCTAssertEqual(lifeCoreIcons.count, 5)  // b01, b04, d07, d08, d09
        for icon in lifeCoreIcons {
            XCTAssertEqual(icon.family, .lifeCore)
        }
    }

    // Test 15: sortOrder 1-24
    func test_sortOrderRange() {
        let orders = AppIconCatalog.allIcons.map(\.sortOrder)
        XCTAssertEqual(orders.min(), 1)
        XCTAssertEqual(orders.max(), 24)
    }

    // Test 16: Icon retrieval by valid ID
    func test_iconByID() {
        let icon = AppIconCatalog.icon(by: "c03_forest_heart")
        XCTAssertNotNil(icon)
        XCTAssertEqual(icon?.displayName, "林息之心")
    }
}
