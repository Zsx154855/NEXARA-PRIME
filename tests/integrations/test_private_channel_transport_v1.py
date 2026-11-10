"""Offline syntactic safety tests; NOT a Mac Relay, Keychain or CAB-01 E2E."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "integrations"))
from private_channel_transport_v1 import (
    ChannelRejected, PinnedPrivateChannel, inspect_reference
)


class PrivateChannelTransportTests(unittest.TestCase):
    NOW = 1790000000

    def setUp(self):
        self.binding = PinnedPrivateChannel(
            repository_id=91001, repository_full_name="fixture-owner/private-mailbox",
            owner_id=48001, issue_number=7)
        self.repo = {
            "id": 91001, "full_name": "fixture-owner/private-mailbox",
            "private": True, "archived": False, "owner": {"id": 48001}
        }
        self.issue = {"number": 7, "state": "open"}
        self.envelope = {
            "schema": 1, "channel_repo_id": 91001, "channel_issue_number": 7,
            "mission_id": "mission_fixture_01", "contract_id": "contract_fixture_01",
            "approval_id": "approval_fixture_01", "nonce": "nonce_fixture_01",
            "signed_sha256": "a" * 64, "issued_at": self.NOW - 10,
            "expires_at": self.NOW + 50,
        }
        self.comment = {"id": 33, "user": {"id": 48001},
                        "body": json.dumps(self.envelope)}

    def check(self):
        return inspect_reference(
            binding=self.binding, github_repository=self.repo,
            github_issue=self.issue, github_comment=self.comment,
            now_epoch=self.NOW)

    def deny(self):
        with self.assertRaises(ChannelRejected):
            self.check()

    def refresh(self):
        self.comment["body"] = json.dumps(self.envelope)

    def test_good_fixture_returns_inert_reference(self):
        result = self.check()
        self.assertEqual(result.status, "TRANSPORT_ONLY_NOT_AUTHORIZED")
        self.assertEqual(result.mission_id, "mission_fixture_01")
        self.assertEqual(len(result.body_sha256), 64)
        self.assertFalse(hasattr(result, "command"))
        self.assertFalse(hasattr(result, "authorized"))

    def test_public_repo_is_denied(self):
        self.repo["private"] = False
        self.deny()

    def test_archived_repo_is_denied(self):
        self.repo["archived"] = True
        self.deny()

    def test_mismatched_repo_identity_is_denied(self):
        self.repo["id"] = 91002
        self.deny()

    def test_spoofed_comment_author_is_denied(self):
        self.comment["user"]["id"] = 48002
        self.deny()

    def test_wrong_mailbox_issue_is_denied(self):
        self.issue["number"] = 56
        self.deny()

    def test_expired_reference_is_denied(self):
        self.envelope["expires_at"] = self.NOW
        self.refresh()
        self.deny()

    def test_excessive_ttl_is_denied(self):
        self.envelope["expires_at"] = self.NOW + 400
        self.refresh()
        self.deny()

    def test_future_reference_is_denied(self):
        self.envelope["issued_at"] = self.NOW + 31
        self.envelope["expires_at"] = self.NOW + 45
        self.refresh()
        self.deny()

    def test_untrusted_command_field_is_denied(self):
        self.envelope["shell"] = "rm -rf /"
        self.refresh()
        self.deny()

    def test_self_asserted_approval_is_denied(self):
        self.envelope["approved"] = True
        self.refresh()
        self.deny()

    def test_duplicate_keys_are_denied(self):
        self.comment["body"] = self.comment["body"].replace(
            '"schema": 1', '"schema": 1, "schema": 1')
        self.deny()

    def test_bad_sha_reference_is_denied(self):
        self.envelope["signed_sha256"] = "fake-signature"
        self.refresh()
        self.deny()

    def test_boolean_numeric_identifier_is_denied(self):
        self.envelope["channel_repo_id"] = True
        self.refresh()
        self.deny()

    def test_non_finite_json_value_is_denied(self):
        self.comment["body"] = self.comment["body"].replace(
            '"schema": 1', '"schema": NaN')
        self.deny()

    def test_oversized_comment_is_denied(self):
        self.comment["body"] = "x" * 4097
        self.deny()

    def test_invalid_pinned_channel_is_denied(self):
        with self.assertRaises(ChannelRejected):
            PinnedPrivateChannel(repository_id=1, repository_full_name="public",
                                 owner_id=5, issue_number=7)


if __name__ == "__main__":
    unittest.main()
