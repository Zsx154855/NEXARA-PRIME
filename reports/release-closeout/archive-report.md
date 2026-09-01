# RELEASE ARCHIVE & INTEGRITY REPORT

## Release Build
- command: xcodebuild build -scheme LivingInterface-iOS -configuration Release
  -destination 'generic/platform=iOS Simulator' -derivedDataPath release/derived-data
  CODE_SIGNING_ALLOWED=NO
- result: BUILD SUCCEEDED
- product: release/derived-data/Build/Products/Release-iphonesimulator/LivingInterface-iOS.app

## Release Archive
- command: xcodebuild archive -configuration Release -archivePath release/archives/LivingInterface-iOS.xcarchive
- result: ARCHIVE SUCCEEDED
- archive: release/archives/LivingInterface-iOS.xcarchive (11M)

## Archive Integrity
- Info.plist: present
- Products/Applications/LivingInterface-iOS.app: present
- dSYMs: present
- Bundle ID: com.nexara.livinginterface.ios
- Version: 0.1.0 (Build 1)
- Executable: LivingInterface-iOS
- CodeSignature: adhoc (LOCAL ARCHIVE, 非发布)
- SHA256(Info.plist): ee2bc05446c0d091371c4876eeb15787b10fc8e56b1b357b88d4426b87feb4c4

## Install/Launch Regression
- install: exit 0
- launch: PID 29743 (无 crash)

## Real Conversation Regression (baseline 一致)
- provider: deepseek (status ok)
- DB quick_check: ok
- mission_ccf6419f2289: state=Completed

## Capacity (外盘策略)
- 内盘: 1.49 GiB → 2.5 GiB (build 后系统回收)
- 外盘: 474.9 GiB (承载 derived-data + archives)
- DerivedData + Archive 全部外盘，内盘零增长压力
