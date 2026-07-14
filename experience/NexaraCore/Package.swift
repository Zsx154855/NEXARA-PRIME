// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "NexaraCore",
    platforms: [.macOS(.v14), .iOS(.v17)],
    products: [
        .library(name: "NexaraCore", targets: ["NexaraCore"]),
    ],
    targets: [
        .target(name: "NexaraCore"),
    ]
)
