# ENVIRONMENT CAPACITY REPORT (V2)

- system_disk: 228Gi total / 3.5Gi avail (APFS container free 3.8GB)
- external_disk: /Volumes/NEXARA 477Gi / 475Gi avail, writable=YES
- xcode: 26.6 (17F113)
- developer_dir: /Applications/Xcode.app/Contents/Developer
- sdk: iPhoneOS26.5 / iPhoneSimulator 26.5
- simulator_runtime: iOS 26.5 (23F77), 5.0G on system disk
- simulator_device: iPhone 15 Pro Max (powered-off)
- deriveddata: ~/Library/Developer/Xcode/DerivedData 91M
- project: LivingInterface 7.6M, 59 swift files, SPM deps=0
- XCODE_EXTERNAL_STORAGE:
  - DerivedData=SUPPORTED (via -derivedDataPath)
  - Archive=SUPPORTED (via -archivePath)
  - Build output=SUPPORTED (DerivedData covers intermediates)
  - Simulator=PARTIAL (runtime 5.0G already on system disk; do not relocate)
- SYSTEM_CAPACITY: CRITICAL (3.5Gi; tiny project → build temps modest)
