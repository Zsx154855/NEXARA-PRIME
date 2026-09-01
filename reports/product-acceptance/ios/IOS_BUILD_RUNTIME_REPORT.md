# IOS BUILD & RUNTIME REPORT (V2)

## Build
- command: xcodebuild -project LivingInterface.xcodeproj -scheme LivingInterface-iOS -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /Volumes/NEXARA/XcodeDerivedData CODE_SIGNING_ALLOWED=NO
- result: BUILD SUCCEEDED (exit 0)
- artifact: /Volumes/NEXARA/XcodeDerivedData/Build/Products/Debug-iphonesimulator/LivingInterface-iOS.app
- bundle_id: com.nexara.livinginterface.ios
- version: 0.1.0
- arch: universal (x86_64 + arm64)
- deriveddata_size: 238M on external disk

## Runtime (Simulator)
- simulator: iOS 26.5 (23F77), iPhone 15 Pro Max (509BDDB3-9542-4C0C-A141-7E97796F92C8)
- boot: OK (Booted)
- install: OK (exit 0)
- launch: OK (PID 85812, UIKitApplication:com.nexara.livinginterface.ios)
- crash: NONE (process alive after 4s)
- system_disk_after: 3.6Gi (stable, external DerivedData did not consume system disk)
