// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "StatusTimer",
    platforms: [.macOS(.v13)],
    targets: [
        .target(name: "TimerCore"),
        .executableTarget(name: "StatusTimer", dependencies: ["TimerCore"]),
        .testTarget(name: "TimerCoreTests", dependencies: ["TimerCore"]),
    ]
)
