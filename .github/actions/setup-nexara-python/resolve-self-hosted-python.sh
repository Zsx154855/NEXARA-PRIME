#!/bin/bash
# ============================================================================
# NEXARA Self-Hosted Python 3.12 Resolver
# ============================================================================
# Resolves a Python 3.12 executable on self-hosted macOS runners,
# creates a per-job isolated virtualenv in $RUNNER_TEMP, and exports
# the virtualenv's bin to $GITHUB_PATH.
#
# NEVER writes to /Users/runner, NEVER calls actions/setup-python download
# path, NEVER depends on shell export or .zshrc.
# ============================================================================
set -euo pipefail

RESOLVED_PYTHON=""
RESOLVED_PATH=""

# -- Candidate resolution (ordered) ------------------------------------------
resolve_python() {
    local candidate
    # C1: explicit override
    if [[ -n "${NEXARA_PYTHON:-}" ]]; then
        candidate="${NEXARA_PYTHON}"
        if verify_python "${candidate}"; then
            RESOLVED_PYTHON="${candidate}"
            return 0
        fi
        echo "[nexara-python] NEXARA_PYTHON set but failed version check: ${candidate}" >&2
    fi

    # C2: command -v python3.12
    if candidate="$(command -v python3.12 2>/dev/null || true)" && [[ -n "${candidate}" ]]; then
        if verify_python "${candidate}"; then
            RESOLVED_PYTHON="${candidate}"
            return 0
        fi
        echo "[nexara-python] command -v python3.12 found ${candidate} but failed version check" >&2
    fi

    # C3: /opt/homebrew/bin/python3.12
    candidate="/opt/homebrew/bin/python3.12"
    if [[ -x "${candidate}" ]]; then
        if verify_python "${candidate}"; then
            RESOLVED_PYTHON="${candidate}"
            return 0
        fi
        echo "[nexara-python] ${candidate} exists but failed version check" >&2
    fi

    # C4: Homebrew python@3.12 prefix
    candidate="/opt/homebrew/opt/python@3.12/bin/python3.12"
    if [[ -x "${candidate}" ]]; then
        if verify_python "${candidate}"; then
            RESOLVED_PYTHON="${candidate}"
            return 0
        fi
        echo "[nexara-python] ${candidate} exists but failed version check" >&2
    fi

    # C5: Framework install
    candidate="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12"
    if [[ -x "${candidate}" ]]; then
        if verify_python "${candidate}"; then
            RESOLVED_PYTHON="${candidate}"
            return 0
        fi
        echo "[nexara-python] ${candidate} exists but failed version check" >&2
    fi

    # C6: pyenv
    if command -v pyenv &>/dev/null; then
        candidate="$(pyenv root)/versions/3.12.*/bin/python3.12"
        # Expand glob
        local expanded
        expanded=$(echo ${candidate} 2>/dev/null || true)
        if [[ -n "${expanded}" && "${expanded}" != "${candidate}" ]]; then
            # Take first match
            local first
            first=$(echo "${expanded}" | head -1)
            if [[ -x "${first}" ]]; then
                if verify_python "${first}"; then
                    RESOLVED_PYTHON="${first}"
                    return 0
                fi
            fi
        fi
    fi

    # C7: repo-governed path (NEXARA_PYTHON_RUNTIME env)
    if [[ -n "${NEXARA_PYTHON_RUNTIME:-}" ]] && [[ -x "${NEXARA_PYTHON_RUNTIME}" ]]; then
        if verify_python "${NEXARA_PYTHON_RUNTIME}"; then
            RESOLVED_PYTHON="${NEXARA_PYTHON_RUNTIME}"
            return 0
        fi
    fi

    return 1
}

# -- Version verification ----------------------------------------------------
verify_python() {
    local py="$1"
    if [[ ! -x "${py}" ]]; then
        echo "[nexara-python] Not executable: ${py}" >&2
        return 1
    fi
    local output
    output=$("${py}" -c "import sys; print(sys.version_info.major); print(sys.version_info.minor)" 2>&1) || {
        echo "[nexara-python] Failed to run version check: ${py}" >&2
        echo "[nexara-python] ${output}" >&2
        return 1
    }
    local major minor
    major=$(echo "${output}" | head -1)
    minor=$(echo "${output}" | head -2 | tail -1)
    if [[ "${major}" != "3" ]]; then
        echo "[nexara-python] Expected major=3, got ${major}: ${py}" >&2
        return 1
    fi
    if [[ "${minor}" != "12" ]]; then
        echo "[nexara-python] Expected minor=12, got ${minor}: ${py}" >&2
        return 1
    fi
    echo "[nexara-python] Verified Python ${major}.${minor}: ${py}" >&2
    return 0
}

# -- Virtualenv creation -----------------------------------------------------
create_venv() {
    local py="$1"
    local venv_dir

    # Use $RUNNER_TEMP if available, otherwise mktemp fallback
    if [[ -n "${RUNNER_TEMP:-}" ]] && [[ -d "${RUNNER_TEMP}" ]]; then
        venv_dir="${RUNNER_TEMP}/nexara-venv-$$-$RANDOM"
    else
        venv_dir="$(mktemp -d 2>/dev/null || mktemp -d -t nexara-venv)"
    fi

    echo "[nexara-python] Creating virtualenv at: ${venv_dir}" >&2
    "${py}" -m venv "${venv_dir}"

    # Verify virtualenv
    local venv_python="${venv_dir}/bin/python"
    if [[ ! -x "${venv_python}" ]]; then
        echo "[nexara-python] ERROR: virtualenv python not found: ${venv_python}" >&2
        return 1
    fi

    "${venv_python}" -c "import sys; print(sys.version_info.major); print(sys.version_info.minor)" >&2
    "${venv_python}" -m pip --version >&2

    # Export virtualenv bin to GITHUB_PATH
    if [[ -n "${GITHUB_PATH:-}" ]]; then
        echo "${venv_dir}/bin" >> "${GITHUB_PATH}"
    fi

    # Set outputs for subsequent steps
    if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
        echo "virtual-env=${venv_dir}" >> "${GITHUB_OUTPUT}"
        echo "python-path=${venv_dir}/bin/python" >> "${GITHUB_OUTPUT}"
        echo "python-version=$("${venv_python}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")')" >> "${GITHUB_OUTPUT}"
    fi

    # Set VIRTUAL_ENV so subsequent steps inherit it
    if [[ -n "${GITHUB_ENV:-}" ]]; then
        echo "VIRTUAL_ENV=${venv_dir}" >> "${GITHUB_ENV}"
        echo "NEXARA_PYTHON=${venv_dir}/bin/python" >> "${GITHUB_ENV}"
    fi

    echo "[nexara-python] VIRTUAL_ENV=${venv_dir}" >&2
    echo "[nexara-python] Virtualenv ready." >&2
    return 0
}

# -- Fail-closed: install python@3.12 if missing -----------------------------
install_python_3_12() {
    echo "[nexara-python] Python 3.12 not found. Checking Homebrew..." >&2

    if ! command -v brew &>/dev/null; then
        echo "[nexara-python] FATAL: Homebrew not available. Cannot install Python 3.12." >&2
        return 1
    fi

    echo "[nexara-python] Installing python@3.12 via Homebrew..." >&2
    brew install python@3.12 2>&1 | while IFS= read -r line; do
        echo "[nexara-python|brew] ${line}" >&2
    done

    if ! command -v python3.12 &>/dev/null; then
        echo "[nexara-python] FATAL: brew install python@3.12 succeeded but python3.12 still not found." >&2
        return 1
    fi

    local installed
    installed="$(command -v python3.12)"
    echo "[nexara-python] Installed: ${installed}" >&2
    python3.12 --version >&2
    return 0
}

# -- Main --------------------------------------------------------------------
main() {
    echo "[nexara-python] NEXARA Self-Hosted Python 3.12 Contract" >&2
    echo "[nexara-python] Runner: self-hosted macOS ARM64 (user: $(whoami))" >&2

    if resolve_python; then
        # Verify resolved path does NOT contain /Users/runner
        if echo "${RESOLVED_PYTHON}" | grep -q "/Users/runner"; then
            echo "[nexara-python] FATAL: Resolved Python path contains /Users/runner — rejected for self-hosted." >&2
            exit 1
        fi
        create_venv "${RESOLVED_PYTHON}"
    elif install_python_3_12; then
        # Re-resolve after install
        if resolve_python; then
            create_venv "${RESOLVED_PYTHON}"
        else
            echo "[nexara-python] FATAL: Installed Python 3.12 but resolve still failed." >&2
            exit 1
        fi
    else
        echo "[nexara-python] FATAL: No Python 3.12 found and install failed." >&2
        echo "[nexara-python] Searched:" >&2
        echo "[nexara-python]   - NEXARA_PYTHON env" >&2
        echo "[nexara-python]   - command -v python3.12" >&2
        echo "[nexara-python]   - /opt/homebrew/bin/python3.12" >&2
        echo "[nexara-python]   - Homebrew python@3.12" >&2
        echo "[nexara-python]   - Framework install" >&2
        echo "[nexara-python]   - pyenv 3.12" >&2
        exit 1
    fi
}

main
