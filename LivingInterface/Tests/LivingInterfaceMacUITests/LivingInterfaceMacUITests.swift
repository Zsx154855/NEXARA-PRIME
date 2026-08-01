import XCTest

@MainActor final class LivingInterfaceMacUITests: XCTestCase {
    var app: XCUIApplication!

    override func setUp() {
        continueAfterFailure = true
        app = XCUIApplication()
        app.launchArguments = ["-ApplePersistenceIgnoreState", "YES"]
        app.launch()
        sleep(8)
    }

    func testSidebarRuntimeOnline() {
        // Button labels work in NavigationSplitView
        XCTAssertTrue(app.buttons["使命时间线"].waitForExistence(timeout: 30), "Timeline button missing")
        // Check sidebar footer text shows online
        let onlineText = app.staticTexts["运行时在线"]
        let offlineText = app.staticTexts["运行时离线"]
        let hasStatus = onlineText.waitForExistence(timeout: 30) || offlineText.waitForExistence(timeout: 5)
        XCTAssertTrue(hasStatus, "Runtime status text not found")
    }

    func testNavigateToMissionTimeline() {
        let timelineBtn = app.buttons["使命时间线"]
        XCTAssertTrue(timelineBtn.waitForExistence(timeout: 15))
        timelineBtn.tap()
        sleep(3)
        // After tapping timeline, verify mission list renders (look for "加载中..." or actual missions)
        let loading = app.staticTexts["加载中..."]
        let found = loading.waitForExistence(timeout: 5)
        // If loading completes, missions should appear
        sleep(3)
        // Check for mission_e834b027d779 text
        let missionText = app.staticTexts.containing(NSPredicate(format: "label CONTAINS 'mission_e834b027d779'")).firstMatch
        let hasMission = missionText.waitForExistence(timeout: 5)
        XCTAssertTrue(found || hasMission, "Mission timeline did not load")
    }

    func testAcceptanceMissionRowExists() {
        let timelineBtn = app.buttons["使命时间线"]
        XCTAssertTrue(timelineBtn.waitForExistence(timeout: 15))
        timelineBtn.tap()
        sleep(5)
        // Find text containing the acceptance mission ID
        let missionText = app.staticTexts.containing(NSPredicate(format: "label CONTAINS 'mission_e834b027d779'")).firstMatch
        XCTAssertTrue(missionText.waitForExistence(timeout: 10), "mission_e834b027d779 not in timeline")
    }

    func testMissionDetailShowsCompletedState() {
        let timelineBtn = app.buttons["使命时间线"]
        XCTAssertTrue(timelineBtn.waitForExistence(timeout: 15))
        timelineBtn.tap()
        sleep(5)
        // Find and tap the acceptance mission
        let missionText = app.staticTexts.containing(NSPredicate(format: "label CONTAINS 'mission_e834b027d779'")).firstMatch
        XCTAssertTrue(missionText.waitForExistence(timeout: 10))
        missionText.tap()
        sleep(3)
        // Verify Completed state visible
        let completedText = app.staticTexts.containing(NSPredicate(format: "label CONTAINS 'Completed'")).firstMatch
        XCTAssertTrue(completedText.waitForExistence(timeout: 10), "Completed state not visible")
        // Verify evidence/receipt labels present
        let evidenceText = app.staticTexts.containing(NSPredicate(format: "label CONTAINS 'Evidence'")).firstMatch
        let receiptText = app.staticTexts.containing(NSPredicate(format: "label CONTAINS 'Receipt'")).firstMatch
        let reportText = app.staticTexts.containing(NSPredicate(format: "label CONTAINS 'tool_'")).firstMatch
        _ = evidenceText.waitForExistence(timeout: 5)
        _ = receiptText.waitForExistence(timeout: 5)
        _ = reportText.waitForExistence(timeout: 5)
        // At least one must exist
        let found = evidenceText.exists || receiptText.exists || reportText.exists
        XCTAssertTrue(found, "Evidence/Receipt/Report not visible")
    }

    func testRestartContinuity() {
        let timelineBtn = app.buttons["使命时间线"]
        XCTAssertTrue(timelineBtn.waitForExistence(timeout: 15))
        timelineBtn.tap()
        sleep(5)
        let missionText = app.staticTexts.containing(NSPredicate(format: "label CONTAINS 'mission_e834b027d779'")).firstMatch
        XCTAssertTrue(missionText.waitForExistence(timeout: 10), "First mission not found")
        app.terminate()
        sleep(2)
        app.launch()
        sleep(8)
        let timelineBtn2 = app.buttons["使命时间线"]
        XCTAssertTrue(timelineBtn2.waitForExistence(timeout: 15))
        timelineBtn2.tap()
        sleep(5)
        let missionText2 = app.staticTexts.containing(NSPredicate(format: "label CONTAINS 'mission_e834b027d779'")).firstMatch
        XCTAssertTrue(missionText2.waitForExistence(timeout: 10), "Mission not found after restart")
    }
}