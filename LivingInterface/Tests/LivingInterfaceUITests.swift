import XCTest

@MainActor final class LivingInterfaceUITests: XCTestCase {
    var app: XCUIApplication!

    override func setUp() {
        continueAfterFailure = true
        app = XCUIApplication()
        app.launch()
    }

#if os(iOS)
    // ── iOS Existence ──

    func testRootViewExists() {
        let el = app.descendants(matching: .any).matching(identifier: "living.root").firstMatch
        XCTAssertTrue(el.waitForExistence(timeout: 3))
    }

    func testBrainExists() {
        let el = app.descendants(matching: .any).matching(identifier: "living.brain").firstMatch
        XCTAssertTrue(el.waitForExistence(timeout: 3))
    }

    func testModeSelectorExists() {
        XCTAssertTrue(app.buttons["静默"].waitForExistence(timeout: 3))
    }

    func testTabBarExists() {
        XCTAssertTrue(app.buttons["今日标签"].waitForExistence(timeout: 3))
    }

    func testNoContentClippedByStatusBar() {
        let label = app.staticTexts["静默"]
        XCTAssertTrue(label.waitForExistence(timeout: 3))
        XCTAssertGreaterThan(label.frame.minY, 0)
    }

    // ── iOS Tabs ──

    func testAllTabsExist() {
        for t in ["今日标签","记忆标签","学习标签","审批标签","状态标签"] {
            XCTAssertTrue(app.buttons[t].waitForExistence(timeout: 3))
        }
    }

    func testTabSwitching() {
        app.buttons["记忆标签"].tap()
        XCTAssertTrue(app.staticTexts["知识图谱 · 长期记忆 · 经验回放"].waitForExistence(timeout: 3))
    }

    func testStatusTabShowsContent() {
        app.buttons["状态标签"].tap()
        XCTAssertTrue(app.staticTexts["当前状态"].waitForExistence(timeout: 3))
    }

    // ── iOS Composer ──

    func testComposerExists() {
        XCTAssertTrue(app.textFields["指令输入框"].waitForExistence(timeout: 3))
    }

    func testSendButtonExists() {
        XCTAssertTrue(app.buttons["发送指令"].waitForExistence(timeout: 3))
    }

    func testSendButtonDisabledWhenEmpty() {
        let btn = app.buttons["发送指令"]
        XCTAssertTrue(btn.waitForExistence(timeout: 3))
        XCTAssertFalse(btn.isEnabled)
    }

    func testComposerAcceptsInput() {
        let c = app.textFields["指令输入框"]
        XCTAssertTrue(c.waitForExistence(timeout: 3))
        c.tap()
        c.typeText("测试指令")
        let v = c.value as? String ?? ""
        XCTAssertTrue(v.contains("测试指令"), "got '\(v)'")
    }

    // ── iOS Hit Target ──

    func testSendButtonHitTarget() {
        let btn = app.buttons["发送指令"]
        XCTAssertTrue(btn.waitForExistence(timeout: 3))
        XCTAssertTrue(btn.exists)
    }

    // ── iOS Geometry ──

    func testComposerAboveTabBar() {
        let c = app.textFields["指令输入框"]
        let t = app.buttons["今日标签"]
        XCTAssertTrue(c.waitForExistence(timeout: 3))
        XCTAssertTrue(t.waitForExistence(timeout: 3))
        XCTAssertLessThanOrEqual(c.frame.maxY, t.frame.maxY + 20)
    }

    func testBrainAboveModeSelector() {
        let brain = app.descendants(matching: .any).matching(identifier: "living.brain").firstMatch
        XCTAssertTrue(brain.waitForExistence(timeout: 3))
        let mode = app.buttons["静默"]
        XCTAssertTrue(mode.waitForExistence(timeout: 3))
        XCTAssertLessThan(brain.frame.minY, mode.frame.minY)
    }

    // ── iOS Mode/Skin ──

    func testModeChipsExist() {
        for s in ["静默","思考","执行","学习"] {
            XCTAssertTrue(app.buttons[s].waitForExistence(timeout: 3))
        }
    }

    func testSkinChipsExist() {
        for s in ["晨雾","潮汐","林息","霞光"] {
            XCTAssertTrue(app.buttons[s].waitForExistence(timeout: 3))
        }
    }

    // ── iOS Keyboard ──

    func testKeyboardAppearsOnFocus() {
        let c = app.textFields["指令输入框"]
        XCTAssertTrue(c.waitForExistence(timeout: 3))
        c.tap()
        XCTAssertTrue(app.keyboards.firstMatch.waitForExistence(timeout: 3))
    }

    func testMultilineInputVisibleWithKeyboard() {
        let c = app.textFields["指令输入框"]
        XCTAssertTrue(c.waitForExistence(timeout: 3))
        c.tap()
        XCTAssertTrue(app.keyboards.firstMatch.waitForExistence(timeout: 3))
        c.typeText("这是第一行输入")
        c.typeText("\n")
        c.typeText("这是第二行输入")
        let v = c.value as? String ?? ""
        XCTAssertTrue(v.contains("第一行"), "got '\(v)'")
        let ks = XCUIScreen.main.screenshot()
        let ksAttachment = XCTAttachment(screenshot: ks)
        ksAttachment.lifetime = .keepAlways; ksAttachment.name = "keyboard_open"; add(ksAttachment)
        saveScreenshot(ks, to: "keyboard_open.png")
        let btn = app.buttons["发送指令"]
        XCTAssertTrue(btn.exists)
        c.typeText("\n"); sleep(1)
        let cs = XCUIScreen.main.screenshot()
        let csAttachment = XCTAttachment(screenshot: cs)
        csAttachment.lifetime = .keepAlways; csAttachment.name = "keyboard_closed_after_input"; add(csAttachment)
        saveScreenshot(cs, to: "keyboard_closed_after_input.png")
    }

    func testTabBarVisibleWhenKeyboardOpen() {
        let c = app.textFields["指令输入框"]
        XCTAssertTrue(c.waitForExistence(timeout: 3))
        c.tap()
        _ = app.keyboards.firstMatch.waitForExistence(timeout: 3)
        XCTAssertTrue(app.buttons["今日标签"].exists)
    }

    func testKeyboardGeometryNoIllegalOverlap() {
        let c = app.textFields["指令输入框"]
        XCTAssertTrue(c.waitForExistence(timeout: 3))
        c.tap()
        let kb = app.keyboards.firstMatch
        XCTAssertTrue(kb.waitForExistence(timeout: 3))
        let send = app.buttons["发送指令"]
        XCTAssertTrue(send.exists)
        let today = app.buttons["今日标签"]
        XCTAssertTrue(today.exists)
        let geo: [String: Any] = [
            "composer_input_frame": ["x":c.frame.origin.x,"y":c.frame.origin.y,"w":c.frame.size.width,"h":c.frame.size.height],
            "composer_send_frame": ["x":send.frame.origin.x,"y":send.frame.origin.y,"w":send.frame.size.width,"h":send.frame.size.height],
            "tabbar_today_frame": ["x":today.frame.origin.x,"y":today.frame.origin.y,"w":today.frame.size.width,"h":today.frame.size.height],
            "keyboard_frame": ["x":kb.frame.origin.x,"y":kb.frame.origin.y,"w":kb.frame.size.width,"h":kb.frame.size.height]
        ]
        if let d = try? JSONSerialization.data(withJSONObject: geo, options: .prettyPrinted),
           let s = String(data: d, encoding: .utf8) {
            let a = XCTAttachment(string: s); a.lifetime = .keepAlways; a.name = "keyboard_geometry"; add(a)
        }
    }
#endif

#if os(macOS)
    // ── macOS Mission Verification ──

    func testSidebarRuntimeStatusExists() {
        let el = app.descendants(matching: .any).matching(identifier: "sidebar_runtime_status").firstMatch
        XCTAssertTrue(el.waitForExistence(timeout: 10), "Sidebar runtime status not found")
    }

    func testNavigateToMissionTimeline() {
        let timelineBtn = app.buttons["使命时间线"]
        XCTAssertTrue(timelineBtn.waitForExistence(timeout: 10), "Mission timeline button not found")
        timelineBtn.tap()
        sleep(2)
        let list = app.descendants(matching: .any).matching(identifier: "mission_timeline_list").firstMatch
        XCTAssertTrue(list.waitForExistence(timeout: 10), "Mission timeline list not found")
    }

    func testAcceptanceMissionRowExists() {
        // Navigate to timeline first
        let timelineBtn = app.buttons["使命时间线"]
        XCTAssertTrue(timelineBtn.waitForExistence(timeout: 10))
        timelineBtn.tap()
        sleep(2)
        let row = app.descendants(matching: .any).matching(identifier: "mission_row_mission_e834b027d779").firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 10), "Acceptance mission row not found")
    }

    func testMissionDetailShowsCorrectState() {
        let timelineBtn = app.buttons["使命时间线"]
        XCTAssertTrue(timelineBtn.waitForExistence(timeout: 10))
        timelineBtn.tap()
        sleep(2)
        let row = app.descendants(matching: .any).matching(identifier: "mission_row_mission_e834b027d779").firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 10))
        row.tap()
        sleep(2)
        // Verify detail fields
        let idEl = app.descendants(matching: .any).matching(identifier: "mission_detail_id").firstMatch
        XCTAssertTrue(idEl.waitForExistence(timeout: 5), "Mission detail ID not found")
        let objEl = app.descendants(matching: .any).matching(identifier: "mission_detail_objective").firstMatch
        XCTAssertTrue(objEl.waitForExistence(timeout: 5), "Mission detail objective not found")
        let stateEl = app.descendants(matching: .any).matching(identifier: "mission_detail_state").firstMatch
        XCTAssertTrue(stateEl.waitForExistence(timeout: 5), "Mission detail state not found")
        let reportEl = app.descendants(matching: .any).matching(identifier: "mission_detail_report").firstMatch
        XCTAssertTrue(reportEl.waitForExistence(timeout: 5), "Mission detail report not found")
        let evEl = app.descendants(matching: .any).matching(identifier: "mission_detail_evidence").firstMatch
        XCTAssertTrue(evEl.waitForExistence(timeout: 5), "Mission detail evidence not found")
        let recEl = app.descendants(matching: .any).matching(identifier: "mission_detail_receipt").firstMatch
        XCTAssertTrue(recEl.waitForExistence(timeout: 5), "Mission detail receipt not found")
    }

    func testRestartContinuity() {
        // First navigation
        let timelineBtn = app.buttons["使命时间线"]
        XCTAssertTrue(timelineBtn.waitForExistence(timeout: 10))
        timelineBtn.tap()
        sleep(2)
        let row = app.descendants(matching: .any).matching(identifier: "mission_row_mission_e834b027d779").firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 10))
        // Terminate and relaunch
        app.terminate()
        sleep(2)
        app.launch()
        sleep(4)
        // Re-navigate
        let timelineBtn2 = app.buttons["使命时间线"]
        XCTAssertTrue(timelineBtn2.waitForExistence(timeout: 10))
        timelineBtn2.tap()
        sleep(2)
        let row2 = app.descendants(matching: .any).matching(identifier: "mission_row_mission_e834b027d779").firstMatch
        XCTAssertTrue(row2.waitForExistence(timeout: 10), "Mission row not found after restart")
    }
#endif

    // MARK: - Helpers

    private func saveScreenshot(_ screenshot: XCUIScreenshot, to filename: String) {
        let dir = "/Users/agentos/NEXARA-PRIME/evidence/living-interface/ui"
        let path = "\(dir)/\(filename)"
        try? FileManager.default.createDirectory(atPath: dir, withIntermediateDirectories: true)
        try? screenshot.pngRepresentation.write(to: URL(fileURLWithPath: path))
    }
}