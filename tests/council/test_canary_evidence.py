"""Verify the GRAND_SLAM_CANARY_RECEIPT_V1.json evidence file."""
import json
import os

import pytest

RECEIPT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "evidence", "receipts",
    "GRAND_SLAM_CANARY_RECEIPT_V1.json"
)

@pytest.fixture
def receipt():
    with open(RECEIPT_PATH) as f:
        return json.load(f)

def test_receipt_exists():
    assert os.path.exists(RECEIPT_PATH), f"Missing: {RECEIPT_PATH}"

def test_receipt_valid_json(receipt):
    assert receipt["receipt_type"] == "GRAND_SLAM_CANARY_RECEIPT"

def test_final_decision_pass(receipt):
    assert receipt["final_decision"] == "PASS"

def test_workers_spawned(receipt):
    w = receipt["worker_spawn_evidence"]
    assert w["total_workers_spawned"] == 2
    assert w["h_code"]["status"] == "PASS"
    assert w["h_mem"]["status"] == "PASS"

def test_zero_human_intervention(receipt):
    assert receipt["zero_human_intervention"]["fully_automated_lifecycle"]

def test_safety_restrictions(receipt):
    s = receipt["safety_restrictions_verified"]
    assert s["no_git_write"]
    assert s["no_deploy"]

def test_authorization(receipt):
    assert "GRAND_SLAM_CONTINUOUS_RUNNER_V1_FULL" in receipt["authorization"]

def test_council_vote_unanimous(receipt):
    votes = receipt["council_vote_authorization"]
    non_approve = [(k, v) for k, v in votes.items() if not str(v).startswith("APPROVE")]
    assert not non_approve, f"Non-approve votes: {non_approve}"
