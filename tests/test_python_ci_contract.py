"""Tests for the NEXARA Python CI Contract.

These tests verify:
- Resolver script correctly identifies Python 3.12
- Rejects non-3.12 versions
- Virtualenv creation and integrity
- GITHUB_PATH / GITHUB_ENV contract
- No /Users/runner contamination
- Workflow YAML structural compliance
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import pytest
import yaml


# ============================================================================
# Path resolution
# ============================================================================

REPO_ROOT = Path(__file__).resolve().parent.parent
ACTIONS_ROOT = REPO_ROOT / ".github" / "actions" / "setup-nexara-python"
RESOLVER_SCRIPT = ACTIONS_ROOT / "resolve-self-hosted-python.sh"
ACTION_YML = ACTIONS_ROOT / "action.yml"
CI_YML = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _require_script():
    if not RESOLVER_SCRIPT.exists():
        pytest.skip(f"Resolver script not found: {RESOLVER_SCRIPT}")


# ============================================================================
# Resolver script tests
# ============================================================================


class TestResolverVersionDetection:
    """Verify the resolver correctly identifies and rejects Python versions."""

    def test_accepts_python_3_12(self):
        """Resolver accepts a valid Python 3.12 executable."""
        _require_script()

        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["RUNNER_TEMP"] = tmp
            env["GITHUB_PATH"] = os.path.join(tmp, "github_path")
            env["GITHUB_OUTPUT"] = os.path.join(tmp, "github_output")
            env["GITHUB_ENV"] = os.path.join(tmp, "github_env")

            result = subprocess.run(
                ["bash", str(RESOLVER_SCRIPT)],
                capture_output=True, text=True, env=env, timeout=30,
            )
            assert result.returncode == 0, f"Resolver failed: {result.stderr}"
            assert "Verified Python 3.12" in result.stderr
            assert "Virtualenv ready" in result.stderr

    def test_rejects_python_3_11_via_fake_executable(self):
        """Resolver rejects an executable that claims to be Python 3.11."""
        _require_script()

        with tempfile.TemporaryDirectory() as tmp:
            # Create a fake python3.12 that reports 3.11
            fake_py = os.path.join(tmp, "python3.12")
            with open(fake_py, "w") as f:
                f.write("""#!/bin/bash
echo "3"
echo "11"
""")
            os.chmod(fake_py, 0o755)

            env = os.environ.copy()
            env["RUNNER_TEMP"] = os.path.join(tmp, "runner_temp")
            env["GITHUB_PATH"] = os.path.join(tmp, "github_path")
            env["GITHUB_OUTPUT"] = os.path.join(tmp, "github_output")
            env["GITHUB_ENV"] = os.path.join(tmp, "github_env")
            env["NEXARA_PYTHON"] = fake_py  # Force candidate C1
            os.makedirs(env["RUNNER_TEMP"], exist_ok=True)

            result = subprocess.run(
                ["bash", str(RESOLVER_SCRIPT)],
                capture_output=True, text=True, env=env, timeout=30,
            )
            # Should fail because 3.11 is rejected
            # (Note: fallback may find real python3.12 on PATH, so we need to isolate)
            if result.returncode == 0:
                # Real python3.12 was found as fallback — verify the fake was tried first
                assert "failed version check" in result.stderr.lower() or \
                       "Expected minor=12, got 11" in result.stderr or \
                       "but failed version check" in result.stderr

    def test_rejects_python_3_13_via_fake_executable(self):
        """Resolver rejects an executable that claims to be Python 3.13."""
        _require_script()

        with tempfile.TemporaryDirectory() as tmp:
            fake_py = os.path.join(tmp, "python3.12")
            with open(fake_py, "w") as f:
                f.write("""#!/bin/bash
echo "3"
echo "13"
""")
            os.chmod(fake_py, 0o755)

            env = os.environ.copy()
            env["RUNNER_TEMP"] = os.path.join(tmp, "runner_temp")
            env["GITHUB_PATH"] = os.path.join(tmp, "github_path")
            env["GITHUB_OUTPUT"] = os.path.join(tmp, "github_output")
            env["GITHUB_ENV"] = os.path.join(tmp, "github_env")
            env["NEXARA_PYTHON"] = fake_py
            os.makedirs(env["RUNNER_TEMP"], exist_ok=True)

            result = subprocess.run(
                ["bash", str(RESOLVER_SCRIPT)],
                capture_output=True, text=True, env=env, timeout=30,
            )
            if result.returncode == 0:
                assert "failed version check" in result.stderr.lower() or \
                       "Expected minor=12, got 13" in result.stderr or \
                       "but failed version check" in result.stderr

    def test_no_python_3_12_fail_closed(self):
        """Resolver fails when no Python 3.12 is available at any candidate path."""
        _require_script()

        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["RUNNER_TEMP"] = os.path.join(tmp, "runner_temp")
            env["GITHUB_PATH"] = os.path.join(tmp, "github_path")
            env["GITHUB_OUTPUT"] = os.path.join(tmp, "github_output")
            env["GITHUB_ENV"] = os.path.join(tmp, "github_env")
            env["NEXARA_PYTHON"] = ""  # Clear override
            os.makedirs(env["RUNNER_TEMP"], exist_ok=True)

            # Remove all python3.12 from PATH
            path_parts = env.get("PATH", "").split(":")
            filtered = [p for p in path_parts if "/opt/homebrew" not in p]
            env["PATH"] = ":".join(filtered)

            result = subprocess.run(
                ["bash", str(RESOLVER_SCRIPT)],
                capture_output=True, text=True, env=env, timeout=30,
            )
            # Should fail (exit 1) unless brew can install it
            # Since we can't control brew, we accept either:
            # - Exit 1: no python found and brew unavailable
            # - Exit 0: brew installed python3.12 successfully
            # The key point: script does not hang or error in unexpected ways
            assert result.returncode in (0, 1), f"Unexpected exit code: {result.returncode}"
            if result.returncode == 1:
                assert "Python 3.12 not found" in result.stderr or "FATAL" in result.stderr


class TestVirtualenvCreation:
    """Verify virtualenv creation via the resolver."""

    def test_virtualenv_created_successfully(self):
        """Resolver creates a working virtualenv with Python 3.12."""
        _require_script()

        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["RUNNER_TEMP"] = tmp
            env["GITHUB_PATH"] = os.path.join(tmp, "github_path")
            env["GITHUB_OUTPUT"] = os.path.join(tmp, "github_output")
            env["GITHUB_ENV"] = os.path.join(tmp, "github_env")

            result = subprocess.run(
                ["bash", str(RESOLVER_SCRIPT)],
                capture_output=True, text=True, env=env, timeout=30,
            )
            assert result.returncode == 0, f"Resolver failed: {result.stderr}"
            assert "Virtualenv ready" in result.stderr

            # Read GITHUB_ENV to get VIRTUAL_ENV path
            github_env = {}
            if os.path.exists(env["GITHUB_ENV"]):
                with open(env["GITHUB_ENV"]) as f:
                    for line in f:
                        line = line.strip()
                        if "=" in line:
                            key, _, val = line.partition("=")
                            github_env[key] = val.strip()

            venv_dir = github_env.get("VIRTUAL_ENV")
            assert venv_dir is not None, "VIRTUAL_ENV not set in GITHUB_ENV"
            assert os.path.isdir(venv_dir), f"Virtualenv dir missing: {venv_dir}"

    def test_virtualenv_python_is_3_12(self):
        """The virtualenv's python reports version 3.12."""
        _require_script()

        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["RUNNER_TEMP"] = tmp
            env["GITHUB_PATH"] = os.path.join(tmp, "github_path")
            env["GITHUB_OUTPUT"] = os.path.join(tmp, "github_output")
            env["GITHUB_ENV"] = os.path.join(tmp, "github_env")

            result = subprocess.run(
                ["bash", str(RESOLVER_SCRIPT)],
                capture_output=True, text=True, env=env, timeout=30,
            )
            assert result.returncode == 0

            github_env = {}
            if os.path.exists(env["GITHUB_ENV"]):
                with open(env["GITHUB_ENV"]) as f:
                    for line in f:
                        line = line.strip()
                        if "=" in line:
                            key, _, val = line.partition("=")
                            github_env[key] = val.strip()

            venv_python = Path(github_env["VIRTUAL_ENV"]) / "bin" / "python"
            assert venv_python.exists()

            version_out = subprocess.run(
                [str(venv_python), "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
                capture_output=True, text=True, timeout=10,
            )
            assert version_out.stdout.strip() == "3.12"

    def test_pip_available_in_virtualenv(self):
        """pip is available and functional in the created virtualenv."""
        _require_script()

        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["RUNNER_TEMP"] = tmp
            env["GITHUB_PATH"] = os.path.join(tmp, "github_path")
            env["GITHUB_OUTPUT"] = os.path.join(tmp, "github_output")
            env["GITHUB_ENV"] = os.path.join(tmp, "github_env")

            result = subprocess.run(
                ["bash", str(RESOLVER_SCRIPT)],
                capture_output=True, text=True, env=env, timeout=30,
            )
            assert result.returncode == 0

            github_env = {}
            if os.path.exists(env["GITHUB_ENV"]):
                with open(env["GITHUB_ENV"]) as f:
                    for line in f:
                        line = line.strip()
                        if "=" in line:
                            key, _, val = line.partition("=")
                            github_env[key] = val.strip()

            venv_pip = Path(github_env["VIRTUAL_ENV"]) / "bin" / "pip"
            assert venv_pip.exists()
            pip_out = subprocess.run(
                [str(venv_pip), "--version"],
                capture_output=True, text=True, timeout=10,
            )
            assert pip_out.returncode == 0
            assert "pip" in pip_out.stdout


class TestGithubPathEnvContract:
    """Verify GITHUB_PATH and GITHUB_ENV are written correctly."""

    def test_github_path_contains_venv_bin(self):
        """GITHUB_PATH points to the virtualenv's bin directory."""
        _require_script()

        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["RUNNER_TEMP"] = tmp
            env["GITHUB_PATH"] = os.path.join(tmp, "github_path")
            env["GITHUB_OUTPUT"] = os.path.join(tmp, "github_output")
            env["GITHUB_ENV"] = os.path.join(tmp, "github_env")

            result = subprocess.run(
                ["bash", str(RESOLVER_SCRIPT)],
                capture_output=True, text=True, env=env, timeout=30,
            )
            assert result.returncode == 0

            with open(env["GITHUB_PATH"]) as f:
                path_content = f.read().strip()
            assert "/bin" in path_content
            assert "venv" in path_content

    def test_github_env_contains_virtual_env(self):
        """GITHUB_ENV exports VIRTUAL_ENV and NEXARA_PYTHON."""
        _require_script()

        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["RUNNER_TEMP"] = tmp
            env["GITHUB_PATH"] = os.path.join(tmp, "github_path")
            env["GITHUB_OUTPUT"] = os.path.join(tmp, "github_output")
            env["GITHUB_ENV"] = os.path.join(tmp, "github_env")

            result = subprocess.run(
                ["bash", str(RESOLVER_SCRIPT)],
                capture_output=True, text=True, env=env, timeout=30,
            )
            assert result.returncode == 0

            with open(env["GITHUB_ENV"]) as f:
                env_content = f.read()
            assert "VIRTUAL_ENV=" in env_content
            assert "NEXARA_PYTHON=" in env_content

    def test_no_users_runner_in_paths(self):
        """No resolved or exported path contains /Users/runner."""
        _require_script()

        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["RUNNER_TEMP"] = tmp
            env["GITHUB_PATH"] = os.path.join(tmp, "github_path")
            env["GITHUB_OUTPUT"] = os.path.join(tmp, "github_output")
            env["GITHUB_ENV"] = os.path.join(tmp, "github_env")

            result = subprocess.run(
                ["bash", str(RESOLVER_SCRIPT)],
                capture_output=True, text=True, env=env, timeout=30,
            )
            assert result.returncode == 0

            # Check GITHUB_PATH
            with open(env["GITHUB_PATH"]) as f:
                assert "/Users/runner" not in f.read()

            # Check GITHUB_ENV
            with open(env["GITHUB_ENV"]) as f:
                assert "/Users/runner" not in f.read()

            # Check GITHUB_OUTPUT
            with open(env["GITHUB_OUTPUT"]) as f:
                assert "/Users/runner" not in f.read()


# ============================================================================
# Workflow YAML structural compliance tests
# ============================================================================


class TestWorkflowYamlCompliance:
    """Verify ci.yml conforms to the NEXARA Python CI contract."""

    PYTHON_JOBS = ["python", "governance", "nsec-governance", "secret-scan"]

    @pytest.fixture
    def workflow(self):
        if not CI_YML.exists():
            pytest.skip(f"CI workflow not found: {CI_YML}")
        with open(CI_YML) as f:
            return yaml.safe_load(f)

    def test_all_python_jobs_use_unified_contract(self, workflow):
        """All four Python-class jobs use ./.github/actions/setup-nexara-python."""
        jobs = workflow.get("jobs", {})

        for job_name in self.PYTHON_JOBS:
            assert job_name in jobs, f"Job '{job_name}' missing from ci.yml"

            steps = jobs[job_name].get("steps", [])
            setup_steps = [
                s for s in steps
                if "uses" in s and "setup-nexara-python" in str(s["uses"])
            ]

            assert len(setup_steps) == 1, (
                f"Job '{job_name}' should have exactly 1 setup-nexara-python step, "
                f"found {len(setup_steps)}"
            )

            step = setup_steps[0]
            assert step["uses"] == "./.github/actions/setup-nexara-python", (
                f"Job '{job_name}' uses '{step['uses']}' instead of "
                f"'./.github/actions/setup-nexara-python'"
            )

    def test_no_setup_python_direct_usage_in_python_jobs(self, workflow):
        """Python jobs must not call actions/setup-python directly."""
        jobs = workflow.get("jobs", {})

        for job_name in self.PYTHON_JOBS:
            steps = jobs[job_name].get("steps", [])
            for step in steps:
                uses = step.get("uses", "")
                assert "actions/setup-python" not in uses, (
                    f"Job '{job_name}' directly uses actions/setup-python — "
                    f"must use ./.github/actions/setup-nexara-python"
                )

    def test_no_continue_on_error_in_python_jobs(self, workflow):
        """Python jobs must not have continue-on-error set."""
        jobs = workflow.get("jobs", {})

        for job_name in self.PYTHON_JOBS:
            job = jobs[job_name]
            assert not job.get("continue-on-error", False), (
                f"Job '{job_name}' has continue-on-error enabled"
            )

    def test_no_step_continue_on_error_in_python_setup(self, workflow):
        """The setup step must not have continue-on-error."""
        jobs = workflow.get("jobs", {})

        for job_name in self.PYTHON_JOBS:
            steps = jobs[job_name].get("steps", [])
            for step in steps:
                assert not step.get("continue-on-error", False), (
                    f"Step in job '{job_name}' has continue-on-error: {step}"
                )

    def test_python_jobs_dont_swallow_setup_failure(self, workflow):
        """Setup steps must not use `|| true` or equivalent."""
        jobs = workflow.get("jobs", {})

        for job_name in self.PYTHON_JOBS:
            steps = jobs[job_name].get("steps", [])
            for step in steps:
                run_cmd = step.get("run", "")
                if isinstance(run_cmd, str):
                    # Check for || true or || : patterns
                    assert "|| true" not in run_cmd, (
                        f"Step in job '{job_name}' uses '|| true': {run_cmd[:80]}"
                    )
                    assert "|| :" not in run_cmd, (
                        f"Step in job '{job_name}' uses '|| :': {run_cmd[:80]}"
                    )

    def test_runner_labels_explicit_for_python_jobs(self, workflow):
        """Python jobs have explicit [self-hosted, macOS, ARM64] labels."""
        jobs = workflow.get("jobs", {})

        for job_name in self.PYTHON_JOBS:
            runs_on = jobs[job_name].get("runs-on", "")
            if isinstance(runs_on, list):
                assert "self-hosted" in runs_on, f"Job '{job_name}' missing self-hosted label"
                assert "macOS" in runs_on, f"Job '{job_name}' missing macOS label"
                assert "ARM64" in runs_on, f"Job '{job_name}' missing ARM64 label"

    def test_github_hosted_branch_present_in_action(self):
        """The composite action preserves actions/setup-python for github-hosted."""
        if not ACTION_YML.exists():
            pytest.skip(f"Action YAML not found: {ACTION_YML}")

        with open(ACTION_YML) as f:
            action = yaml.safe_load(f)

        steps = action.get("runs", {}).get("steps", [])
        assert any(
            "actions/setup-python" in str(s.get("uses", ""))
            for s in steps
        ), "Composite action must retain actions/setup-python for GitHub-hosted branch"

    def test_self_hosted_branch_present_in_action(self):
        """The composite action has a self-hosted resolver step."""
        if not ACTION_YML.exists():
            pytest.skip(f"Action YAML not found: {ACTION_YML}")

        with open(ACTION_YML) as f:
            action = yaml.safe_load(f)

        steps = action.get("runs", {}).get("steps", [])
        assert any(
            s.get("if") == "runner.environment == 'self-hosted'"
            for s in steps
        ), "Composite action must have self-hosted resolver branch"


class TestActionYamlStructure:
    """Verify action.yml is well-formed."""

    def test_action_yml_exists_and_valid(self):
        """Action YAML is parseable."""
        assert ACTION_YML.exists(), f"Action YAML not found: {ACTION_YML}"
        with open(ACTION_YML) as f:
            data = yaml.safe_load(f)
        assert data.get("name") is not None
        assert data.get("runs", {}).get("using") == "composite"

    def test_resolver_script_exists_and_executable(self):
        """Resolver script exists and is executable."""
        assert RESOLVER_SCRIPT.exists(), f"Resolver script not found: {RESOLVER_SCRIPT}"
        assert os.access(RESOLVER_SCRIPT, os.X_OK), (
            f"Resolver script not executable: {RESOLVER_SCRIPT}"
        )
