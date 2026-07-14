// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "NexaraIOS",
    platforms: [.iOS(.v17), .macOS(.v14)],
    dependencies: [
        .package(path: "../NexaraCore"),
    ],
    targets: [
        .executableTarget(
            name: "NexaraIOS",
            dependencies: ["NexaraCore"],
            path: "Sources/NexaraIOS"
        ),
    ]
)
