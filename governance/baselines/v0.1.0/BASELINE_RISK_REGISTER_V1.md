# Baseline Risk Register — v0.1.0

| ID       | Risk                                       | Likelihood | Impact    | Mitigation                                      | Status |
|----------|--------------------------------------------|------------|-----------|-------------------------------------------------|--------|
| RISK-001 | external_signing_blocked                    | High       | Critical  | Obtain Apple Developer Program membership + certificate | OPEN   |
| RISK-002 | notarization_blocked                       | High       | Critical  | Requires signing certificate; submit to Apple notary | OPEN   |
| RISK-003 | ios_ipa_blocked                            | High       | Critical  | Requires iOS provisioning profile + Apple Developer account | OPEN   |
| RISK-004 | brand_name_pending                         | Medium     | Medium    | Complete legal trademark search; file if clear   | OPEN   |
| RISK-005 | single_developer_repo                      | Medium     | Medium    | Onboard additional maintainers; document bus factor | OPEN   |
| RISK-006 | no_ci_configured                           | High       | Medium    | Set up GitHub Actions or equivalent CI pipeline  | OPEN   |
| RISK-007 | hdiutil_sandbox_blocked                    | Medium     | High      | Work around macOS sandbox restrictions for hdiutil; use script-sandbox entitlement | OPEN   |

## Risk Details

### RISK-001: external_signing_blocked
Apple Developer Program membership or code signing certificate not yet acquired. Without signing, the DMG and app bundle cannot be distributed outside the local build machine.

### RISK-002: notarization_blocked
Notarization requires a valid signing certificate and Apple Developer Program membership. Without notarization, macOS Gatekeeper will block users from launching the app.

### RISK-003: ios_ipa_blocked
iOS IPA generation requires a paid Apple Developer account, a provisioning profile, and a distribution certificate. The IPA target cannot be tested on physical devices until these are in place.

### RISK-004: brand_name_pending
The "Nexara Prime" brand name has not undergone legal trademark clearance. If another entity holds a conflicting trademark, renaming may be required before public launch.

### RISK-005: single_developer_repo
The repository currently has a single active developer. All code, reviews, releases, and infrastructure depend on one individual, creating a bus-factor risk.

### RISK-006: no_ci_configured
No continuous integration pipeline (GitHub Actions, GitLab CI, etc.) is configured. Builds, tests, and releases are performed manually on a single workstation.

### RISK-007: hdiutil_sandbox_blocked
macOS sandbox restrictions may prevent `hdiutil create` from running in CI or restricted environments. A `script-sandbox` entitlement or alternative tool (create-dmg, node-dmg-builder) may be required.
