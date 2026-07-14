import SwiftUI

@main
struct NexaraMacApp: App {
    @StateObject private var model = RuntimeViewModel()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(model)
                .frame(minWidth: 900, idealWidth: 1200, minHeight: 640, idealHeight: 800)
        }
        .windowStyle(.titleBar)
        .windowToolbarStyle(.unified(showsTitle: true))
        .commands {
            CommandGroup(replacing: .newItem) {}
            SidebarCommands()
        }
    }
}
