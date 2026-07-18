"""V13 regression tests — adversarial validation of 7 Codex review threads.

Thread coverage:
  1. Indirect braced secret expansions (${!TOKEN}, ${!API_KEY})
  2. HOME credential path coverage ($HOME/${HOME} .config/gh, .netrc, .pypirc, .git-credentials)
  3. Forced git switch -f/--force detection
  4. Git fetch/remote/config argument-aware classification
  5. Arbitrary interpreter script file execution → R3+
  6. date/hostname parameter-aware classification
  7. find file-output action detection (-fprint, -fprintf, -fls)
"""

from __future__ import annotations


from src.nexara_prime.aos.command_classifier import (
    RiskLevel,
    CommandClassifier,
    _has_secret_expansion,
    _find_has_output_action,
    _find_output_target,
)


classifier = CommandClassifier()


# ═══════════════════════════════════════════════════════════════════════════════
# Thread 1: Indirect braced secret expansions
# ═══════════════════════════════════════════════════════════════════════════════

class TestIndirectBracedSecretExpansion:
    """Thread 1 (Codex V13): ${!TOKEN} must be R4."""

    def test_indirect_token_expansion_r4(self):
        """echo foo ${!TOKEN} → R4"""
        result = classifier.classify("echo foo ${!TOKEN}")
        assert result.risk_level == RiskLevel.R4, f"Expected R4, got {result.risk_level}"
        assert result.kind.value == "secret"

    def test_indirect_api_key_expansion_r4(self):
        """echo ${!API_KEY} → R4"""
        result = classifier.classify("echo ${!API_KEY}")
        assert result.risk_level == RiskLevel.R4, f"Expected R4, got {result.risk_level}"

    def test_indirect_quoted_expansion_r4(self):
        '''echo "${!TOKEN}" → R4'''
        result = classifier.classify('echo "${!TOKEN}"')
        assert result.risk_level == RiskLevel.R4, f"Expected R4, got {result.risk_level}"

    def test_indirect_secret_expansion_r4(self):
        """echo ${!SECRET} → R4"""
        result = classifier.classify("echo ${!SECRET}")
        assert result.risk_level == RiskLevel.R4, f"Expected R4, got {result.risk_level}"

    def test_indirect_password_expansion_r4(self):
        """echo ${!PASSWORD} → R4"""
        result = classifier.classify("echo ${!PASSWORD}")
        assert result.risk_level == RiskLevel.R4, f"Expected R4, got {result.risk_level}"

    def test_indirect_aws_expansion_r4(self):
        """echo ${!AWS_SECRET_ACCESS_KEY} → R4"""
        result = classifier.classify("echo ${!AWS_SECRET_ACCESS_KEY}")
        assert result.risk_level == RiskLevel.R4, f"Expected R4, got {result.risk_level}"

    def test_direct_braced_expansion_still_r4(self):
        """echo ${TOKEN} still R4 (regression check)"""
        result = classifier.classify("echo ${TOKEN}")
        assert result.risk_level == RiskLevel.R4, f"Expected R4, got {result.risk_level}"

    def test_braced_with_modifier_still_r4(self):
        """echo ${TOKEN:-default} still R4"""
        result = classifier.classify("echo ${TOKEN:-default}")
        assert result.risk_level == RiskLevel.R4, f"Expected R4, got {result.risk_level}"

    def test_safe_home_expansion_not_r4_secret(self):
        """echo HOME is safe — verify secret detection doesn't flag it (pre-existing echo $ pattern may catch)"""
        has_secret = _has_secret_expansion("echo ${HOME}")
        assert not has_secret, "echo ${HOME} should NOT be detected as secret expansion"

    def test_safe_user_expansion_not_r4_secret(self):
        """echo USER is safe — verify secret detection doesn't flag it"""
        has_secret = _has_secret_expansion("echo ${USER}")
        assert not has_secret, "echo ${USER} should NOT be detected as secret expansion"


# ═══════════════════════════════════════════════════════════════════════════════
# Thread 2: HOME credential path coverage
# ═══════════════════════════════════════════════════════════════════════════════

class TestHomeCredentialPathCoverage:
    """Thread 2 (Codex V13): $HOME/${HOME} forms for all credential files."""

    def test_dollar_home_config_gh_r4(self):
        """cat $HOME/.config/gh/hosts.yml → R4"""
        result = classifier.classify("cat $HOME/.config/gh/hosts.yml")
        assert result.risk_level == RiskLevel.R4, f"Expected R4, got {result.risk_level}"

    def test_braced_home_config_gh_r4(self):
        """cat ${HOME}/.config/gh/hosts.yml → R4"""
        result = classifier.classify("cat ${HOME}/.config/gh/hosts.yml")
        assert result.risk_level == RiskLevel.R4, f"Expected R4, got {result.risk_level}"

    def test_dollar_home_netrc_r4(self):
        """cat $HOME/.netrc → R4"""
        result = classifier.classify("cat $HOME/.netrc")
        assert result.risk_level == RiskLevel.R4, f"Expected R4, got {result.risk_level}"

    def test_braced_home_netrc_r4(self):
        """cat ${HOME}/.netrc → R4"""
        result = classifier.classify("cat ${HOME}/.netrc")
        assert result.risk_level == RiskLevel.R4, f"Expected R4, got {result.risk_level}"

    def test_dollar_home_pypirc_r4(self):
        """cat $HOME/.pypirc → R4"""
        result = classifier.classify("cat $HOME/.pypirc")
        assert result.risk_level == RiskLevel.R4, f"Expected R4, got {result.risk_level}"

    def test_braced_home_pypirc_r4(self):
        """cat ${HOME}/.pypirc → R4"""
        result = classifier.classify("cat ${HOME}/.pypirc")
        assert result.risk_level == RiskLevel.R4, f"Expected R4, got {result.risk_level}"

    def test_dollar_home_git_credentials_r4(self):
        """cat $HOME/.git-credentials → R4"""
        result = classifier.classify("cat $HOME/.git-credentials")
        assert result.risk_level == RiskLevel.R4, f"Expected R4, got {result.risk_level}"

    def test_braced_home_git_credentials_r4(self):
        """cat ${HOME}/.git-credentials → R4"""
        result = classifier.classify("cat ${HOME}/.git-credentials")
        assert result.risk_level == RiskLevel.R4, f"Expected R4, got {result.risk_level}"

    def test_root_netrc_r4(self):
        """cat /root/.netrc → R4"""
        result = classifier.classify("cat /root/.netrc")
        assert result.risk_level == RiskLevel.R4, f"Expected R4, got {result.risk_level}"

    def test_root_pypirc_r4(self):
        """cat /root/.pypirc → R4"""
        result = classifier.classify("cat /root/.pypirc")
        assert result.risk_level == RiskLevel.R4, f"Expected R4, got {result.risk_level}"

    def test_root_git_credentials_r4(self):
        """cat /root/.git-credentials → R4"""
        result = classifier.classify("cat /root/.git-credentials")
        assert result.risk_level == RiskLevel.R4, f"Expected R4, got {result.risk_level}"

    def test_root_config_gh_r4(self):
        """cat /root/.config/gh/hosts.yml → R4"""
        result = classifier.classify("cat /root/.config/gh/hosts.yml")
        assert result.risk_level == RiskLevel.R4, f"Expected R4, got {result.risk_level}"

    def test_tilde_config_gh_still_r4(self):
        """cat ~/.config/gh/hosts.yml → R4 (regression)"""
        result = classifier.classify("cat ~/.config/gh/hosts.yml")
        assert result.risk_level == RiskLevel.R4, f"Expected R4, got {result.risk_level}"

    def test_normal_file_not_r4(self):
        """cat README.md NOT R4"""
        result = classifier.classify("cat README.md")
        assert result.risk_level != RiskLevel.R4, f"README.md should not be R4, got {result.risk_level}"


# ═══════════════════════════════════════════════════════════════════════════════
# Thread 3: Forced git switch -f/--force
# ═══════════════════════════════════════════════════════════════════════════════

class TestForcedGitSwitch:
    """Thread 3 (Codex V13): git switch -f/--force must be destructive."""

    def test_switch_f_main_destructive(self):
        """git switch -f main → destructive (R3+)"""
        result = classifier.classify("git switch -f main")
        assert result.risk_level in (RiskLevel.R3, RiskLevel.R4), f"Expected R3+, got {result.risk_level}"

    def test_switch_force_main_destructive(self):
        """git switch --force main → destructive"""
        result = classifier.classify("git switch --force main")
        assert result.risk_level in (RiskLevel.R3, RiskLevel.R4), f"Expected R3+, got {result.risk_level}"

    def test_switch_force_create_still_destructive(self):
        """git switch -C main → destructive (regression)"""
        result = classifier.classify("git switch -C main")
        assert result.risk_level in (RiskLevel.R3, RiskLevel.R4), f"Expected R3+, got {result.risk_level}"

    def test_switch_discard_changes_still_destructive(self):
        """git switch --discard-changes main → destructive (regression)"""
        result = classifier.classify("git switch --discard-changes main")
        assert result.risk_level in (RiskLevel.R3, RiskLevel.R4), f"Expected R3+, got {result.risk_level}"

    def test_switch_f_specific_file_destructive(self):
        """git switch -f feature/foo → destructive"""
        result = classifier.classify("git switch -f feature/foo")
        assert result.risk_level in (RiskLevel.R3, RiskLevel.R4), f"Expected R3+, got {result.risk_level}"

    def test_normal_switch_is_r2(self):
        """git switch main → R2 (not destructive)"""
        result = classifier.classify("git switch main")
        assert result.risk_level == RiskLevel.R2, f"Expected R2, got {result.risk_level}"

    def test_checkout_f_still_destructive(self):
        """git checkout -f main → destructive (regression)"""
        result = classifier.classify("git checkout -f main")
        assert result.risk_level in (RiskLevel.R3, RiskLevel.R4), f"Expected R3+, got {result.risk_level}"


# ═══════════════════════════════════════════════════════════════════════════════
# Thread 4: Git fetch/remote/config argument-aware
# ═══════════════════════════════════════════════════════════════════════════════

class TestGitFetchRemoteConfig:
    """Thread 4 (Codex V13): fetch/remote/config NOT unconditionally R0."""

    # ── fetch ──
    def test_fetch_default_r2(self):
        """git fetch → R2 (not R0)"""
        result = classifier.classify("git fetch")
        assert result.risk_level == RiskLevel.R2, f"Expected R2, got {result.risk_level}"

    def test_fetch_prune_r3(self):
        """git fetch --prune → R3"""
        result = classifier.classify("git fetch --prune")
        assert result.risk_level == RiskLevel.R3, f"Expected R3, got {result.risk_level}"

    def test_fetch_dry_run_r0(self):
        """git fetch --dry-run → R0"""
        result = classifier.classify("git fetch --dry-run")
        assert result.risk_level == RiskLevel.R0, f"Expected R0, got {result.risk_level}"

    def test_fetch_all_r2(self):
        """git fetch --all → R2"""
        result = classifier.classify("git fetch --all")
        assert result.risk_level == RiskLevel.R2, f"Expected R2, got {result.risk_level}"

    # ── remote ──
    def test_remote_v_r0(self):
        """git remote -v → R0"""
        result = classifier.classify("git remote -v")
        assert result.risk_level == RiskLevel.R0, f"Expected R0, got {result.risk_level}"

    def test_remote_show_r0(self):
        """git remote show origin → R0"""
        result = classifier.classify("git remote show origin")
        assert result.risk_level == RiskLevel.R0, f"Expected R0, got {result.risk_level}"

    def test_remote_add_r2(self):
        """git remote add upstream <url> → R2+"""
        result = classifier.classify("git remote add upstream https://github.com/user/repo")
        assert result.risk_level not in (RiskLevel.R0,), f"Should not be R0, got {result.risk_level}"

    def test_remote_remove_r2(self):
        """git remote remove origin → R2+"""
        result = classifier.classify("git remote remove origin")
        assert result.risk_level not in (RiskLevel.R0,), f"Should not be R0, got {result.risk_level}"

    def test_remote_set_url_r2(self):
        """git remote set-url origin <url> → R2+"""
        result = classifier.classify("git remote set-url origin https://github.com/user/repo")
        assert result.risk_level not in (RiskLevel.R0,), f"Should not be R0, got {result.risk_level}"

    # ── config ──
    def test_config_get_r0(self):
        """git config --get user.email → R0"""
        result = classifier.classify("git config --get user.email")
        assert result.risk_level == RiskLevel.R0, f"Expected R0, got {result.risk_level}"

    def test_config_list_r0(self):
        """git config --list → R0"""
        result = classifier.classify("git config --list")
        assert result.risk_level == RiskLevel.R0, f"Expected R0, got {result.risk_level}"

    def test_config_global_write_r3(self):
        """git config --global user.email x → R3"""
        result = classifier.classify("git config --global user.email x@y.com")
        assert result.risk_level == RiskLevel.R3, f"Expected R3, got {result.risk_level}"

    def test_config_system_write_r3(self):
        """git config --system core.editor vim → R3"""
        result = classifier.classify("git config --system core.editor vim")
        assert result.risk_level == RiskLevel.R3, f"Expected R3, got {result.risk_level}"

    def test_config_add_r2(self):
        """git config --add remote.origin.fetch +refs/heads/* → R2"""
        result = classifier.classify("git config --add remote.origin.fetch +refs/heads/*:refs/remotes/origin/*")
        assert result.risk_level == RiskLevel.R2, f"Expected R2, got {result.risk_level}"

    def test_config_unset_r2(self):
        """git config --unset user.name → R2"""
        result = classifier.classify("git config --unset user.name")
        assert result.risk_level == RiskLevel.R2, f"Expected R2, got {result.risk_level}"

    def test_config_global_get_r0(self):
        """git config --global --get user.email → R0 (read even with --global)"""
        result = classifier.classify("git config --global --get user.email")
        assert result.risk_level == RiskLevel.R0, f"Expected R0, got {result.risk_level}"

    def test_config_set_value_r2(self):
        """git config user.email test@test.com → R2 (bare set)"""
        result = classifier.classify("git config user.email test@test.com")
        assert result.risk_level == RiskLevel.R2, f"Expected R2, got {result.risk_level}"


# ═══════════════════════════════════════════════════════════════════════════════
# Thread 5: Arbitrary interpreter script file execution
# ═══════════════════════════════════════════════════════════════════════════════

class TestArbitraryInterpreterScript:
    """Thread 5 (Codex V13): python script.py → R3+ (not R1/R0)."""

    def test_python_script_r3(self):
        """python tools/cleanup.py → R3+"""
        result = classifier.classify("python tools/cleanup.py")
        assert result.risk_level in (RiskLevel.R3, RiskLevel.R4), f"Expected R3+, got {result.risk_level}"

    def test_node_script_r3(self):
        """node scripts/task.js → R3+"""
        result = classifier.classify("node scripts/task.js")
        assert result.risk_level in (RiskLevel.R3, RiskLevel.R4), f"Expected R3+, got {result.risk_level}"

    def test_ruby_script_r3(self):
        """ruby script.rb → R3+"""
        result = classifier.classify("ruby script.rb")
        assert result.risk_level in (RiskLevel.R3, RiskLevel.R4), f"Expected R3+, got {result.risk_level}"

    def test_bash_script_r3(self):
        """bash script.sh → R3+"""
        result = classifier.classify("bash script.sh")
        assert result.risk_level in (RiskLevel.R3, RiskLevel.R4), f"Expected R3+, got {result.risk_level}"

    def test_sh_script_r3(self):
        """sh script.sh → R3+"""
        result = classifier.classify("sh script.sh")
        assert result.risk_level in (RiskLevel.R3, RiskLevel.R4), f"Expected R3+, got {result.risk_level}"

    def test_pytest_still_r1(self):
        """pytest → R1 (known-safe tool)"""
        result = classifier.classify("pytest")
        assert result.risk_level == RiskLevel.R1, f"Expected R1, got {result.risk_level}"

    def test_ruff_check_still_r1(self):
        """ruff check → R1 (known-safe tool)"""
        result = classifier.classify("ruff check")
        assert result.risk_level == RiskLevel.R1, f"Expected R1, got {result.risk_level}"

    def test_python_m_pytest_still_r1(self):
        """python -m pytest → R1"""
        result = classifier.classify("python -m pytest")
        assert result.risk_level == RiskLevel.R1, f"Expected R1, got {result.risk_level}"

    def test_python_m_not_script(self):
        """python -m json.tool → not caught as script execution"""
        result = classifier.classify("python -m json.tool")
        assert result.risk_level != RiskLevel.R3, f"-m modules should not be R3, got {result.risk_level}"

    def test_python_c_still_r2_r4(self):
        """python -c 'print(1)' → R2+ (interpreter snippet, not script file)"""
        result = classifier.classify("python -c 'print(1)'")
        assert result.risk_level in (RiskLevel.R2, RiskLevel.R4), f"Expected R2+, got {result.risk_level}"


# ═══════════════════════════════════════════════════════════════════════════════
# Thread 6: date/hostname parameter-aware
# ═══════════════════════════════════════════════════════════════════════════════

class TestDateHostnameParameterAware:
    """Thread 6 (Codex V13): date/hostname NOT unconditionally R0."""

    # ── date ──
    def test_date_read_only_r0(self):
        """date → R0"""
        result = classifier.classify("date")
        assert result.risk_level == RiskLevel.R0, f"Expected R0, got {result.risk_level}"

    def test_date_format_r0(self):
        """date +%F → R0"""
        result = classifier.classify("date +%F")
        assert result.risk_level == RiskLevel.R0, f"Expected R0, got {result.risk_level}"

    def test_date_u_r0(self):
        """date -u → R0"""
        result = classifier.classify("date -u")
        assert result.risk_level == RiskLevel.R0, f"Expected R0, got {result.risk_level}"

    def test_date_set_r4(self):
        """date -s '2024-01-01' → R4"""
        result = classifier.classify("date -s '2024-01-01'")
        assert result.risk_level == RiskLevel.R4, f"Expected R4, got {result.risk_level}"

    def test_date_set_long_r4(self):
        """date --set '2024-01-01' → R4"""
        result = classifier.classify("date --set '2024-01-01'")
        assert result.risk_level == RiskLevel.R4, f"Expected R4, got {result.risk_level}"

    def test_date_set_with_format_r4(self):
        '''date -s "2024-01-01 12:00" → R4'''
        result = classifier.classify('date -s "2024-01-01 12:00"')
        assert result.risk_level == RiskLevel.R4, f"Expected R4, got {result.risk_level}"

    # ── hostname ──
    def test_hostname_read_only_r0(self):
        """hostname → R0"""
        result = classifier.classify("hostname")
        assert result.risk_level == RiskLevel.R0, f"Expected R0, got {result.risk_level}"

    def test_hostname_f_r0(self):
        """hostname -f → R0"""
        result = classifier.classify("hostname -f")
        assert result.risk_level == RiskLevel.R0, f"Expected R0, got {result.risk_level}"

    def test_hostname_short_r0(self):
        """hostname -s → R0"""
        result = classifier.classify("hostname -s")
        assert result.risk_level == RiskLevel.R0, f"Expected R0, got {result.risk_level}"

    def test_hostname_set_r4(self):
        """hostname new-hostname → R4"""
        result = classifier.classify("hostname new-hostname")
        assert result.risk_level == RiskLevel.R4, f"Expected R4, got {result.risk_level}"

    def test_hostname_set_fqdn_r4(self):
        """hostname new.example.com → R4"""
        result = classifier.classify("hostname new.example.com")
        assert result.risk_level == RiskLevel.R4, f"Expected R4, got {result.risk_level}"

    # ── hostnamectl ──
    def test_hostnamectl_set_hostname_r4(self):
        """hostnamectl set-hostname new-name → R4"""
        result = classifier.classify("hostnamectl set-hostname new-name")
        assert result.risk_level == RiskLevel.R4, f"Expected R4, got {result.risk_level}"

    def test_hostnamectl_status_r0(self):
        """hostnamectl status → R0"""
        result = classifier.classify("hostnamectl status")
        assert result.risk_level == RiskLevel.R0, f"Expected R0, got {result.risk_level}"


# ═══════════════════════════════════════════════════════════════════════════════
# Thread 7: find file-output action detection
# ═══════════════════════════════════════════════════════════════════════════════

class TestFindFileOutputActions:
    """Thread 7 (Codex V13): find -fprint/-fprintf/-fls must NOT be R0."""

    def test_find_fprint_r2(self):
        """find . -fprint /tmp/out → R2+ (not R0)"""
        result = classifier.classify("find . -fprint /tmp/out")
        assert result.risk_level not in (RiskLevel.R0,), f"Should not be R0, got {result.risk_level}"

    def test_find_fprint0_r2(self):
        """find . -fprint0 /tmp/out → R2+"""
        result = classifier.classify("find . -fprint0 /tmp/out")
        assert result.risk_level not in (RiskLevel.R0,), f"Should not be R0, got {result.risk_level}"

    def test_find_fprintf_r2(self):
        """find . -fprintf /tmp/out '%p\n' → R2+"""
        result = classifier.classify("find . -fprintf /tmp/out '%p\\n'")
        assert result.risk_level not in (RiskLevel.R0,), f"Should not be R0, got {result.risk_level}"

    def test_find_fls_r2(self):
        """find . -fls /tmp/out → R2+"""
        result = classifier.classify("find . -fls /tmp/out")
        assert result.risk_level not in (RiskLevel.R0,), f"Should not be R0, got {result.risk_level}"

    def test_find_fprint_etc_r4(self):
        """find . -fprint /etc/motd → R4 (system path)"""
        result = classifier.classify("find . -fprint /etc/motd")
        assert result.risk_level in (RiskLevel.R3, RiskLevel.R4), f"Expected R3+, got {result.risk_level}"

    def test_find_fprintf_etc_r4(self):
        """find . -fprintf /etc/cron.d/job '%p\n' → R4"""
        result = classifier.classify("find . -fprintf /etc/cron.d/job '%p\\n'")
        assert result.risk_level in (RiskLevel.R3, RiskLevel.R4), f"Expected R3+, got {result.risk_level}"

    def test_find_normal_r0(self):
        """find . -name '*.py' → R0 (regression)"""
        result = classifier.classify("find . -name '*.py'")
        assert result.risk_level == RiskLevel.R0, f"Expected R0, got {result.risk_level}"

    def test_find_delete_still_detected(self):
        """find . -delete → not R0 (regression)"""
        result = classifier.classify("find . -delete")
        assert result.risk_level != RiskLevel.R0, f"Should not be R0, got {result.risk_level}"

    def test_find_exec_still_detected(self):
        """find . -exec rm {} \\; → not R0 (regression)"""
        result = classifier.classify("find . -exec rm {} \\;")
        assert result.risk_level != RiskLevel.R0, f"Should not be R0, got {result.risk_level}"

    # ── Helper function tests ──
    def test_find_has_output_action_true(self):
        assert _find_has_output_action("find . -fprint /tmp/out") is True
        assert _find_has_output_action("find . -fprint0 /tmp/out") is True
        assert _find_has_output_action("find . -fprintf /tmp/out '%p'") is True
        assert _find_has_output_action("find . -fls /tmp/out") is True

    def test_find_has_output_action_false(self):
        assert _find_has_output_action("find . -name '*.py'") is False
        assert _find_has_output_action("find . -type f") is False

    def test_find_output_target(self):
        assert _find_output_target("find . -fprint /tmp/out") == "/tmp/out"
        assert _find_output_target("find . -fprintf /tmp/out '%p'") == "/tmp/out"
        assert _find_output_target("find . -fls /tmp/ls.txt") == "/tmp/ls.txt"


# ═══════════════════════════════════════════════════════════════════════════════
# Integration: combined adversarial tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestAdversarialV13Integration:
    """Cross-cutting adversarial tests from the full spec list."""

    def test_git_log_grep_commit_r0(self):
        """git log --grep=commit → R0 (token-parsed, commit is grep pattern)"""
        result = classifier.classify("git log --grep=commit")
        assert result.risk_level == RiskLevel.R0, f"Expected R0, got {result.risk_level}"

    def test_git_diff_origin_push_fix_r0(self):
        """git diff origin/push-fix → R0 (push in ref name, not subcommand)"""
        result = classifier.classify("git diff origin/push-fix")
        assert result.risk_level == RiskLevel.R0, f"Expected R0, got {result.risk_level}"

    def test_git_show_commit123_r0(self):
        """git show commit123 → R0 (commit123 is revision, not subcommand)"""
        result = classifier.classify("git show commit123")
        assert result.risk_level == RiskLevel.R0, f"Expected R0, got {result.risk_level}"

    def test_git_diff_output_etc_r4(self):
        """git diff --output=/etc/x → R3+ (system path, may be R3 or R4)"""
        result = classifier.classify("git diff --output=/etc/x")
        assert result.risk_level in (RiskLevel.R3, RiskLevel.R4), f"Expected R3+, got {result.risk_level}"

    def test_git_checkout_readme_destructive(self):
        """git checkout README.md → destructive"""
        result = classifier.classify("git checkout README.md")
        assert result.risk_level in (RiskLevel.R3, RiskLevel.R4), f"Expected R3+, got {result.risk_level}"

    def test_git_checkout_dot_destructive(self):
        """git checkout . → destructive"""
        result = classifier.classify("git checkout .")
        assert result.risk_level in (RiskLevel.R3, RiskLevel.R4), f"Expected R3+, got {result.risk_level}"


# ═══════════════════════════════════════════════════════════════════════════════
# V11/V12 thread verification — BLOCK recovery, capabilities, idempotency, grants
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# V11/V12 thread verification — existing code is already correct.
# These tests verify that the implemented fixes work correctly.
# ═══════════════════════════════════════════════════════════════════════════════

class TestBlockRecoveryTerminal:
    """Thread V11-3: BLOCK recovery must return terminal failure, not requeue."""

    def test_block_strategy_returns_failure(self):
        """RecoveryStrategy.BLOCK → success=False"""
        from nexara_prime.aos.recovery_engine import (
            RecoveryEngine, RecoveryStrategy,
        )

        engine = RecoveryEngine(max_retries=3)
        result = engine.recover(
            mission_id="m1", failure_type="worker_crash",
            attempt=7,  # index 6=BLOCK
        )
        assert result.success is False, f"BLOCK must fail, got success={result.success}"
        assert result.strategy == RecoveryStrategy.BLOCK

    def test_block_strategy_is_terminal(self):
        """When strategy is BLOCK or ESCALATE, it's terminal."""
        from nexara_prime.aos.recovery_engine import (
            RecoveryEngine,
        )

        engine = RecoveryEngine(max_retries=0, circuit_breaker_threshold=1)
        result = engine.recover(
            mission_id="m2", failure_type="worker_crash",
            attempt=1,
        )
        assert result.success is False, "Terminal recovery must return success=False"


class TestEmptyCapabilitiesRejection:
    """Thread V12-4: Empty capabilities must not satisfy custom requirements."""

    def test_empty_caps_no_docker(self):
        """Worker with empty capabilities does NOT match docker requirement."""
        from nexara_prime.orchestration import WorkerScheduler
        from nexara_prime.models import WorkerDescriptor
        from nexara_prime.aos.worker_adapters import WorkerType

        scheduler = WorkerScheduler.__new__(WorkerScheduler)
        worker = WorkerDescriptor(
            worker_id="w1", worker_type=WorkerType.LOCAL_TOOL,
            writer_capable=True, health="healthy",
            capabilities=[],  # empty!
        )
        assert scheduler._capability_match(worker, ["docker"]) is False, (
            "Empty capabilities must NOT satisfy docker"
        )

    def test_empty_caps_no_gpu(self):
        """Worker with empty capabilities does NOT match gpu requirement."""
        from nexara_prime.orchestration import WorkerScheduler
        from nexara_prime.models import WorkerDescriptor
        from nexara_prime.aos.worker_adapters import WorkerType

        scheduler = WorkerScheduler.__new__(WorkerScheduler)
        worker = WorkerDescriptor(
            worker_id="w2", worker_type=WorkerType.CLAUDE,
            writer_capable=True, health="healthy",
            capabilities=[],  # empty!
        )
        assert scheduler._capability_match(worker, ["gpu"]) is False, (
            "Empty capabilities must NOT satisfy gpu"
        )

    def test_explicit_caps_satisfy(self):
        """Worker with explicitly declared docker DOES match."""
        from nexara_prime.orchestration import WorkerScheduler
        from nexara_prime.models import WorkerDescriptor
        from nexara_prime.aos.worker_adapters import WorkerType

        scheduler = WorkerScheduler.__new__(WorkerScheduler)
        worker = WorkerDescriptor(
            worker_id="w3", worker_type=WorkerType.LOCAL_TOOL,
            writer_capable=True, health="healthy",
            capabilities=["docker"],
        )
        assert scheduler._capability_match(worker, ["docker"]) is True, (
            "Worker with explicit docker capability must match"
        )


class TestIdempotentPayloadFirstWriteWins:
    """Thread V12-1 / V11-4: First-write payload must never be overwritten."""

    def test_same_key_returns_existing(self):
        """Same idempotency_key returns EXISTING_ITEM, not CREATED_NEW."""
        from nexara_prime.orchestration import MissionQueue, EnqueueStatus
        from nexara_prime.models import MissionQueueItem, QueueItemState
        from nexara_prime.events import EventBus
        from nexara_prime.db import SQLiteStore
        import tempfile
        import os

        db_path = os.path.join(tempfile.mkdtemp(), "test.db")
        store = SQLiteStore(db_path)
        events = EventBus(store)
        mq = MissionQueue(store, events)

        item = MissionQueueItem(
            mission_id="m1", state=QueueItemState.QUEUED,
            idempotency_key="key-abc", priority=5,
        )
        r1 = mq.enqueue(item, new_payload_hash="hash123")
        assert r1.status == EnqueueStatus.CREATED_NEW

        # Same key — must return existing
        item2 = MissionQueueItem(
            mission_id="m2", state=QueueItemState.QUEUED,
            idempotency_key="key-abc", priority=5,
        )
        r2 = mq.enqueue(item2, new_payload_hash="hash123")
        assert r2.status == EnqueueStatus.EXISTING_ITEM, f"Expected EXISTING_ITEM, got {r2.status}"
        # Original mission_id preserved
        assert r2.item.mission_id == "m1", "Original mission_id must be preserved"

    def test_different_payload_conflict(self):
        """Same key, different payload → IDEMPOTENCY_CONFLICT."""
        from nexara_prime.orchestration import MissionQueue, EnqueueStatus
        from nexara_prime.models import MissionQueueItem, QueueItemState
        from nexara_prime.events import EventBus
        from nexara_prime.db import SQLiteStore
        import tempfile
        import os

        db_path = os.path.join(tempfile.mkdtemp(), "test.db")
        store = SQLiteStore(db_path)
        events = EventBus(store)
        mq = MissionQueue(store, events)

        item = MissionQueueItem(
            mission_id="m1", state=QueueItemState.QUEUED,
            idempotency_key="key-def", priority=5,
        )
        mq.enqueue(item, new_payload_hash="hash_alpha")

        # Different payload — must conflict
        item2 = MissionQueueItem(
            mission_id="m3", state=QueueItemState.QUEUED,
            idempotency_key="key-def", priority=5,
        )
        r2 = mq.enqueue(item2, new_payload_hash="hash_beta")
        assert r2.status == EnqueueStatus.IDEMPOTENCY_CONFLICT, (
            f"Expected IDEMPOTENCY_CONFLICT, got {r2.status}"
        )


class TestGrantBindingPreCasValidation:
    """Thread V11-2: Grant command/mission binding checked before atomic consume."""

    def test_grant_command_mismatch_blocked(self):
        """Grant for 'echo a' must not be consumed by 'echo b'."""
        from nexara_prime.aos.execution_gateway import (
            ExecutionGateway, ApprovalGrant,
        )
        from nexara_prime.aos.worker_adapters import DeterministicFakeWorker
        from nexara_prime.models import WorkerDescriptor
        from nexara_prime.models import WorkerType
        from unittest.mock import MagicMock

        worker = DeterministicFakeWorker(
            WorkerDescriptor(
                worker_id="w1", worker_type=WorkerType.LOCAL_TOOL,
                writer_capable=True, health="healthy",
            )
        )
        gw = ExecutionGateway()
        gw._workers = {"w1": worker}
        gw.set_approval_verifier(MagicMock(return_value=True))

        grant = ApprovalGrant(
            mission_id="m1", command="echo hello", run_id="r1",
            approval_id="a1", nonce="n1",
        )
        # Different command — grant must NOT be consumed
        result = gw.dispatch(
            worker_id="w1", mission_id="m1",
            input_data={"command": "echo world"},
            approval_grant=grant,
        )
        assert result.success is False, "Command mismatch must block dispatch"

    def test_grant_mission_id_mismatch_blocked(self):
        """Grant for mission m1 must not be consumed by mission m2."""
        from nexara_prime.aos.execution_gateway import (
            ExecutionGateway, ApprovalGrant,
        )
        from nexara_prime.aos.worker_adapters import DeterministicFakeWorker
        from nexara_prime.models import WorkerDescriptor
        from nexara_prime.models import WorkerType
        from unittest.mock import MagicMock

        worker = DeterministicFakeWorker(
            WorkerDescriptor(
                worker_id="w1", worker_type=WorkerType.LOCAL_TOOL,
                writer_capable=True, health="healthy",
            )
        )
        gw = ExecutionGateway()
        gw._workers = {"w1": worker}
        gw.set_approval_verifier(MagicMock(return_value=True))

        grant = ApprovalGrant(
            mission_id="m1", command="echo hello", run_id="r1",
            approval_id="a1", nonce="n1",
        )
        # Different mission_id — grant must NOT be consumed
        result = gw.dispatch(
            worker_id="w1", mission_id="m2",
            input_data={"command": "echo hello"},
            approval_grant=grant,
        )
        assert result.success is False, "Mission ID mismatch must block dispatch"
