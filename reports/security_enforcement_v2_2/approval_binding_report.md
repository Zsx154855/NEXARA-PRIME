# Approval Binding Report
- removed approved=True boolean
- invoke() requires approval_id + actor_id
- _validate_approval looks up real ApprovalStore
- Validates: status=APPROVED, mission match, not expired, not consumed
- Single-action approvals consumed after first use
- 7 verification tests pass
