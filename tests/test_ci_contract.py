"""CI Workflow Contract Tests — fail-closed patterns."""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CI_FILE = REPO / ".github/workflows/ci.yml"


class TestIosBuildFailClosed:
    def test_no_xcodebuild_fail_open(self) -> None:
        """xcodebuild must not be masked by || echo."""
        content = CI_FILE.read_text()
        for i, line in enumerate(content.split("\n"), 1):
            if "xcodebuild" in line:
                # Check that this xcodebuild block does NOT have || echo after it
                block = content.split("\n")[i-1:i+10]
                block_text = "\n".join(block)
                has_fail_open = "|| echo" in block_text and "xcodebuild" in block_text
                assert not has_fail_open, (
                    "L{}: xcodebuild with fail-open || echo detected:\n{}".format(i, block_text[:200])
                )

    def test_ios_step_has_set_e(self) -> None:
        """iOS build steps must use set -euo pipefail."""
        content = CI_FILE.read_text()
        # Find the iOS build step
        in_ios = False
        found_set_e = False
        for line in content.split("\n"):
            if "Build iOS Simulator" in line:
                in_ios = True
            if in_ios and "set -euo pipefail" in line:
                found_set_e = True
                break
            if in_ios and line.strip().startswith("- name:") and "iOS" not in line:
                break
        assert found_set_e, "iOS build step must use set -euo pipefail"

    def test_no_allow_failure_on_build_jobs(self) -> None:
        """Build verification jobs must not have continue-on-error."""
        # Only artifact upload can have continue-on-error
        content = CI_FILE.read_text()
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "continue-on-error" in line:
                # Check context — only allowed for artifact upload
                context = "\n".join(lines[max(0,i-3):i+3])
                assert "upload-artifact" in context, (
                    "continue-on-error only allowed for artifact upload. Found at L{}:\n{}".format(
                        i+1, context)
                )


class TestCiWorkflowStructure:
    def test_ci_file_exists_and_valid_yaml(self) -> None:
        import yaml
        assert CI_FILE.exists()
        yaml.safe_load(CI_FILE.read_text())

    def test_all_required_jobs_present(self) -> None:
        content = CI_FILE.read_text()
        required = ["python:", "typescript:", "swift-macos:", "swift-ios:",
                    "governance:", "nsec-governance:", "secret-scan:", "sovereign-delivery:"]
        for job in required:
            assert job in content, "Missing required job: {}".format(job)

    def test_xcodebuild_has_explicit_scheme(self) -> None:
        """xcodebuild must use explicit scheme, not glob fallback."""
        content = CI_FILE.read_text()
        # The SCHEME variable must be set before xcodebuild
        if "xcodebuild" in content:
            idx = content.index("xcodebuild")
            preceding = content[max(0,idx-500):idx]
            assert "SCHEME" in preceding, "xcodebuild must use explicit SCHEME variable"
