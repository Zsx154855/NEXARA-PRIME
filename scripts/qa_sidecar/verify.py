#!/usr/bin/env python3
"""NEXARA read-only QA evidence verifier. Fails closed without independent identity."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

FILES = ('focused.log', 'full.log', 'commit-sha.txt', 'git-status.txt',
         'final-report.txt', 'log-sha256.txt')
SHA = re.compile(r'[0-9a-f]{40}\Z')
DIGEST = re.compile(r'[0-9a-f]{64}\Z')

class Blocked(Exception):
    pass

def read_regular(p):
    if p.is_symlink() or not p.is_file():
        raise Blocked('missing_or_symlink:' + p.name)
    return p.read_bytes()

def digest(data):
    return hashlib.sha256(data).hexdigest()

def field(txt, key):
    values = re.findall(r'^' + re.escape(key) + r'=([^\r\n]*)$', txt, re.M)
    if len(values) != 1:
        raise Blocked('missing_or_duplicate_field:' + key)
    return values[0].strip()

def git(repo, *args):
    p = subprocess.run(['git', '-C', str(repo), *args], capture_output=True,
                       text=True, timeout=10)
    if p.returncode:
        raise Blocked('git_check_failed:' + args[0])
    return p.stdout.strip()

def within(path, folder):
    path, folder = path.resolve(), folder.resolve()
    return path == folder or folder in path.parents

def assess(args):
    repo, root = args.repo.resolve(), args.evidence.resolve()
    if not SHA.fullmatch(args.sha):
        raise Blocked('invalid_commit_sha')
    if within(root, repo):
        raise Blocked('evidence_inside_worktree')
    if git(repo, 'rev-parse', 'HEAD') != args.sha or git(repo, 'status', '--porcelain'):
        raise Blocked('git_sha_mismatch_or_dirty')
    data = {name: read_regular(root / name) for name in FILES}
    if data['commit-sha.txt'].decode().strip() != args.sha or data['git-status.txt'].strip():
        raise Blocked('evidence_git_binding_mismatch')
    final = data['final-report.txt'].decode()
    expected = {'HEAD': args.sha, 'FOCUSED_EXIT': '0', 'FULL_EXIT': '0',
                'WORKTREE_CLEAN': 'YES', 'REGRESSION': 'PASS'}
    for k, v in expected.items():
        if field(final, k) != v:
            raise Blocked('reported_result_mismatch:' + k)
    expected_hashes = {}
    for line in data['log-sha256.txt'].decode().splitlines():
        m = re.fullmatch(r'([0-9a-f]{64})\s+\*?(.+)', line)
        if not m:
            raise Blocked('invalid_hash_line')
        name = Path(m.group(2)).name
        if name not in ('focused.log', 'full.log') or name in expected_hashes:
            raise Blocked('unknown_or_duplicate_hash')
        expected_hashes[name] = m.group(1)
    if set(expected_hashes) != {'focused.log', 'full.log'}:
        raise Blocked('missing_hash')
    for name, want in expected_hashes.items():
        if digest(data[name]) != want:
            raise Blocked('tampered:' + name)
    focused, full = data['focused.log'].decode(), data['full.log'].decode()
    focused_n = re.findall(r'^\s*(\d+) passed in [\d.]+s\s*$', focused, re.M)
    full_n = re.findall(r'^\s*(\d+) passed, (\d+) subtests passed in [\d.]+s\s*$', full, re.M)
    if len(focused_n) != 1 or len(full_n) != 1:
        raise Blocked('pytest_summary_missing_or_ambiguous')
    if int(focused_n[0]) < args.min_focused or int(full_n[0][0]) < args.min_full:
        raise Blocked('test_count_below_policy')
    if args.min_focused < 1 or args.min_full < 1:
        raise Blocked('invalid_policy_minimum')
    return {
        'schema': 'nexara.qa-sidecar.evidence.v1',
        'repository': args.repo_id,
        'commit_sha': args.sha,
        'observed': {'focused_passed': int(focused_n[0]),
                     'full_passed': int(full_n[0][0]),
                     'subtests_passed': int(full_n[0][1])},
        'artifact_sha256': {name: digest(data[name]) for name in sorted(data)},
    }

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, required=True)
    p.add_argument('--evidence', type=Path, required=True)
    p.add_argument('--repo-id', default='Zsx154855/NEXARA-PRIME')
    p.add_argument('--sha', required=True)
    p.add_argument('--min-focused', type=int, default=5)
    p.add_argument('--min-full', type=int, default=2445)
    p.add_argument('--statement-out', type=Path)
    p.add_argument('--signature', type=Path)
    p.add_argument('--trusted-signers', type=Path)
    p.add_argument('--trusted-signers-sha256')
    p.add_argument('--principal')
    a = p.parse_args()
    try:
        statement = assess(a)
        wire = json.dumps(statement, sort_keys=True, separators=(',', ':')).encode()
        if a.statement_out:
            if a.statement_out.exists() or a.statement_out.is_symlink():
                raise Blocked('statement_output_already_exists')
            a.statement_out.write_bytes(wire)
        attrs = (a.signature, a.trusted_signers, a.trusted_signers_sha256, a.principal)
        signed = any(attrs)
        if signed and not all(attrs):
            raise Blocked('incomplete_signature_parameters')
        if signed:
            if not DIGEST.fullmatch(a.trusted_signers_sha256):
                raise Blocked('invalid_trust_anchor_digest')
            if within(a.trusted_signers, a.repo) or within(a.trusted_signers, a.evidence):
                raise Blocked('trust_anchor_must_be_external')
            if digest(read_regular(a.trusted_signers)) != a.trusted_signers_sha256:
                raise Blocked('trust_anchor_digest_mismatch')
            if a.signature.is_symlink() or not a.signature.is_file():
                raise Blocked('missing_signature')
            ssh = shutil.which('ssh-keygen')
            if not ssh:
                raise Blocked('ssh_keygen_missing')
            result = subprocess.run(
                [ssh, '-Y', 'verify', '-f', str(a.trusted_signers), '-I', a.principal,
                 '-n', 'nexara-qa-sidecar-v1', '-s', str(a.signature)],
                input=wire, capture_output=True, timeout=15)
            if result.returncode:
                raise Blocked('signature_invalid')
        print(json.dumps({'technical': 'PASS', 'signature': 'VALID' if signed else 'ABSENT',
                          'independent_identity': 'NOT_VERIFIED', 'gate': 'QA_BLOCKED',
                          'statement_sha256': digest(wire), 'observed': statement['observed']},
                         sort_keys=True))
        return 2  # Even a valid signature is not proof of independently controlled custody.
    except (Blocked, ValueError, UnicodeError, OSError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({'technical': 'BLOCKED', 'gate': 'QA_BLOCKED',
                          'reason': str(exc)}), file=sys.stderr)
        return 3

if __name__ == '__main__':
    sys.exit(main())
