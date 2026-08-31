# ACCESSIBILITY & PERFORMANCE REPORT (V2)

## Accessibility
- contract: NO explicit accessibility contract found (no AXE requirement in acceptance docs)
- swiftui_annotations: 73 accessibilityLabel/Identifier/Element markers in LivingInterface
- AXE: NOT_RUN (no tool installed, no contract requires it)
- verdict: ACCESSIBILITY_STATIC = PARTIAL (73 static markers present, no runtime AXE scan)
  - AXE = NOT_REQUIRED (no contract)

## Performance Baseline (M1 MBA / 8GB, Xcode 26.6, Python 3.12)
- health: 0.129s
- conversations list: 0.042s
- conversation create: 0.041s
- sqlite read (records count): 0.004s
- baseline_created: YES
