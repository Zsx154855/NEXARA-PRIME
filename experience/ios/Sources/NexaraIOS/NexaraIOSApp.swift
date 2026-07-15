import NexaraCore
import SwiftUI

@main
struct NexaraIOSApp: App {
    @StateObject private var model = IOSRuntimeViewModel()

    var body: some Scene {
        WindowGroup {
            AdaptiveContentView()
                .environmentObject(model)
        }
    }
}
