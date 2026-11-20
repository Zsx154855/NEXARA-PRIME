"""Private local P3 write boundary. No public HTTP route or production startup."""

from dataclasses import dataclass
import datetime as dt
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import tempfile
import time

from durable import digest, stopped
from p2_broker import _encoded, _peer_uid, _receive, _trusted_directory
from p2_missions import LocalMissionController, MissionBlocked, task_from
import relay
from p3_dsh import DSH_ARGUMENTS, MAX_TASK_SECONDS, TASK_KINDS, DshError, dsh_evidence, run_task, task_arguments, verify_dsh_evidence


APPROVAL_NS = "nexara-p3-approval"
RECEIPT_NS = "nexara-p3-receipt"
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{2,79}")
HEX = re.compile(r"[a-f0-9]{64}")
CONTRACT = {"contract_id", "mission_id", "requester_uid", "requester", "approver", "revision",
            "workspace", "head", "allowed_operations", "expires_at", "status", "max_seconds",
            "budget_microusd", "test_id"}
GRANT = {"approval_id", "principal", "task_sha256", "contract_sha256", "issued_at"}


class Denied(MissionBlocked):
    pass


@dataclass(frozen=True)
class Identity:
    public_key: str
    role: str


def _is_id(value):
    return isinstance(value, str) and ID.fullmatch(value)


def _hash(value):
    return digest(relay.json_canonical(value))


def _verify(identity, principal, expected_role, namespace, value, signature):
    if (not _is_id(principal) or not isinstance(identity, Identity) or identity.role != expected_role
            or not re.fullmatch(r"ssh-ed25519 [A-Za-z0-9+/]{68}=?", identity.public_key)
            or not isinstance(signature, str) or len(signature) > 1024
            or not signature.startswith("-----BEGIN SSH SIGNATURE-----\n")):
        raise Denied("identity_or_signature_rejected")
    try:
        with tempfile.TemporaryDirectory(prefix="nexara-p3-verification-") as directory:
            temp = Path(directory)
            (temp / "signers").write_text(f"{principal} {identity.public_key}\n")
            (temp / "signature").write_text(signature)
            verify = subprocess.run(
                ["/usr/bin/ssh-keygen", "-Y", "verify", "-f", str(temp / "signers"), "-I", principal,
                 "-n", namespace, "-s", str(temp / "signature")],
                input=relay.json_canonical(value).encode(), stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, cwd="/", env={}, timeout=3,
            )
        if verify.returncode:
            raise Denied("identity_or_signature_rejected")
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        raise Denied("identity_or_signature_rejected") from exc


class Admission:
    """The host pins keys and the local contract path before it accepts requests."""

    def __init__(self, contract_path, identities, workspace, git_head, *, now=None):
        self.contract_path, self.identities = contract_path, dict(identities)
        keys = [identity.public_key for identity in self.identities.values() if isinstance(identity, Identity)]
        if (len(keys) != len(self.identities) or len(keys) != len(set(keys))
                or not all(_is_id(name) and identity.role in {"approver", "worker"}
                           for name, identity in self.identities.items())):
            raise Denied("identity_registry_invalid")
        self.workspace, self.git_head = workspace, git_head
        self.now = now or (lambda: dt.datetime.now(dt.timezone.utc))

    def check(self, request, peer_uid):
        try:
            return self._check(request, peer_uid)
        except (MissionBlocked, relay.RelayError, OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
            raise Denied("private_admission_denied") from exc

    def _check(self, request, peer_uid):
        if type(request) is not dict or set(request) != {"task", "grant", "signature"}:
            raise Denied("request_schema")
        task = task_from(request["task"], self.workspace)
        grant = request["grant"]
        if type(grant) is not dict or set(grant) != GRANT or not _is_id(grant["approval_id"]):
            raise Denied("grant_schema")
        principal = grant["principal"]
        if not _is_id(principal):
            raise Denied("identity_rejected")
        _verify(self.identities.get(principal), principal, "approver", APPROVAL_NS, grant, request["signature"])
        contract = relay.private_json(self.contract_path, 4096)
        if type(contract) is not dict or set(contract) != CONTRACT:
            raise Denied("contract_schema")
        now = self.now()
        issued = relay.parse_utc(grant["issued_at"])
        if (not dt.timedelta(0) <= now - issued <= dt.timedelta(seconds=300)
                or not now < relay.parse_utc(contract["expires_at"])
                or contract["status"] != "active" or contract["mission_id"] != task.mission_id
                or not _is_id(contract["contract_id"]) or not _is_id(contract["test_id"])
                or type(contract["revision"]) is not int or contract["revision"] < 1
                or type(contract["requester_uid"]) is not int or contract["requester_uid"] != peer_uid
                or not _is_id(contract["requester"]) or contract["requester"] == principal
                or getattr(self.identities.get(contract["requester"]), "role", None) != "worker"
                or contract["approver"] != principal or contract["workspace"] != self.workspace
                or contract["head"] != self.git_head()
                or contract["allowed_operations"] not in (["repo.apply_patch"], ["dsh.task.run"])
                or task.operation != contract["allowed_operations"][0]
                or type(contract["budget_microusd"]) is not int or contract["budget_microusd"] != 0
                or type(contract["max_seconds"]) is not int or not 1 <= contract["max_seconds"] <= 20
                or grant["task_sha256"] != task.request_hash or grant["contract_sha256"] != _hash(contract)):
            raise Denied("grant_scope")
        if task.operation == "dsh.task.run":
            _check_dsh_arguments(task, contract)
        return {**grant, "contract": contract, "signed_grant_sha256": _hash(
            {"grant": grant, "signature": request["signature"]})}


def _check_dsh_arguments(task, contract):
    """dsh.task.run is narrower than repo.apply_patch: a fixed task kind and a bound instruction."""
    try:
        args = task_arguments(task)
    except (ValueError, TypeError, RecursionError) as exc:
        raise Denied("dsh_arguments") from exc
    if (not isinstance(args, dict) or set(args) != DSH_ARGUMENTS
            or args.get("task_kind") not in TASK_KINDS
            or not isinstance(args.get("instruction"), str) or not args["instruction"]
            or not isinstance(args.get("route"), dict)
            or set(args["route"]) != {"kind", "endpoint"}
            or not isinstance(args["route"].get("kind"), str)
            or not isinstance(args["route"].get("endpoint"), str) or not args["route"]["endpoint"]
            or not isinstance(args.get("instruction_sha256"), str)
            or digest(args["instruction"]) != args["instruction_sha256"]
            or type(contract.get("max_seconds")) is not int
            or contract["max_seconds"] > MAX_TASK_SECONDS):
        raise Denied("dsh_arguments")


class PrivateMissionController(LocalMissionController):
    database_name = "p3-private.sqlite3"

    def __enter__(self):
        if os.path.lexists(self.folder / LocalMissionController.database_name):
            raise Denied("p2_lane_forbidden")
        return super().__enter__()


class PrivateWrite:
    def __init__(self, ledger, workspace, admission, dsh_adapter=None):
        self.ledger, self.workspace, self.admission = ledger, workspace, admission
        self.dsh_adapter = dsh_adapter
        if workspace.binding() != admission.workspace:
            raise Denied("workspace_mismatch")

    def accept(self, connection, allowed_uid):
        peer_uid = _peer_uid(connection)
        if peer_uid != allowed_uid:
            raise Denied("peer_denied")
        request = _receive(connection, 4096, time.monotonic() + 3)
        if stopped(self.ledger):
            return {"status": "STOPPED"}
        approved = self.admission.check(request, peer_uid)
        task = task_from(request["task"], self.admission.workspace)
        args = task.arguments
        if task.operation == "dsh.task.run":
            if set(args) != DSH_ARGUMENTS:
                raise Denied("test_scope_rejected")
        elif (set(args) != {"path", "old_sha256", "content"} or not isinstance(args["content"], str)
                or not self.workspace.has_fixture_check(
                    approved["contract"]["test_id"], args["path"], digest(args["content"]))):
            raise Denied("test_scope_rejected")
        grant_deadline = time.monotonic() + approved["contract"]["max_seconds"]

        def admit(candidate):
            current = self.admission.check(request, peer_uid)
            if (candidate != task or current["signed_grant_sha256"] != approved["signed_grant_sha256"]
                    or time.monotonic() >= grant_deadline):
                raise Denied("dispatch_rejected")
            return approved["approval_id"]

        def invoke(operation, args):
            state = worker.status(task.mission_id, task.task_id)
            contract = approved["contract"]
            if operation == "dsh.task.run":
                if set(args) != DSH_ARGUMENTS:
                    raise Denied("operation_rejected")
                if admit(task) != approved["approval_id"] or self.workspace.head() != contract["head"]:
                    raise Denied("dispatch_rejected")
                if stopped(self.ledger):
                    raise Denied("dispatch_rejected")
                dispatch_time = self.admission.now().isoformat()
                try:
                    outcome = run_task(workspace=self.workspace.path,
                                       instruction=args["instruction"],
                                       timeout=contract["max_seconds"],
                                       route=args["route"],
                                       adapter=self.dsh_adapter)
                except DshError as exc:
                    raise Denied(str(exc)) from exc
                times = (dispatch_time, self.admission.now().isoformat())
                _check_execution_times(approved, times)
                return dsh_evidence(approved, task, state, outcome, times)
            if operation != "repo.apply_patch" or set(args) != {"path", "old_sha256", "content"}:
                raise Denied("operation_rejected")
            if admit(task) != approved["approval_id"] or self.workspace.head() != contract["head"]:
                raise Denied("dispatch_rejected")
            before = self.workspace.execute("files.read", {"path": args["path"]})["sha256"]
            if before != args["old_sha256"] or stopped(self.ledger):
                raise Denied("stale_file")
            if admit(task) != approved["approval_id"] or stopped(self.ledger):
                raise Denied("dispatch_rejected")
            dispatch_time = self.admission.now().isoformat()
            patch = self.workspace.execute(operation, args)
            if time.monotonic() >= grant_deadline:
                raise Denied("write_outcome_unverified")
            test = self.workspace.execute("test.run", {"command_id": contract["test_id"]})
            after = self.workspace.execute("files.read", {"path": args["path"]})["sha256"]
            if (after != patch["sha256"] or self.workspace.head() != contract["head"]
                    or time.monotonic() >= grant_deadline):
                raise Denied("write_outcome_unverified")
            times = (dispatch_time, self.admission.now().isoformat())
            _check_execution_times(approved, times)
            return execution_evidence(approved, task, state, before, after, test, times)

        with PrivateMissionController(self.ledger, self.admission.workspace, admit, invoke) as worker:
            worker.enqueue(request["task"])
            worker.run(task.mission_id, task.task_id)
            row = worker.row(task.mission_id, task.task_id)
            result = worker.status(task.mission_id, task.task_id)
            if row["evidence"] and digest(row["evidence"]) == row["evidence_sha256"]:
                result["evidence"] = relay.strict_json(row["evidence"])
            return result


def _check_execution_times(approved, times):
    dispatch, finish = (relay.parse_utc(value) for value in times)
    issued = relay.parse_utc(approved["issued_at"])
    contract = approved["contract"]
    if (not issued <= dispatch <= finish < relay.parse_utc(contract["expires_at"])
            or finish - issued > dt.timedelta(seconds=300)
            or type(contract["max_seconds"]) is not int or not 1 <= contract["max_seconds"] <= 20
            or finish - dispatch > dt.timedelta(seconds=contract["max_seconds"])):
        raise Denied("execution_time_unverified")


def execution_evidence(approved, task, state, before, after, test, times):
    contract, args = approved["contract"], task.arguments
    return {
        "scope": "local_p3", "mission_id": task.mission_id, "contract_id": contract["contract_id"],
        "approval_principal": approved["principal"], "approval_sha256": approved["signed_grant_sha256"],
        "task_id": task.task_id, "attempt_id": state["attempt_id"], "execution_epoch": state["epoch"],
        "dispatched_at": times[0], "finished_at": times[1],
        "workspace_sha256": task.workspace, "git_head": contract["head"],
        "allowed_operations": [*contract["allowed_operations"], "test.run"],
        "tool": task.operation, "parameters_sha256": _hash(args),
        "file": {"path": args["path"], "before_sha256": before, "after_sha256": after},
        "test": {"command_id": test["command_id"], "exit_code": test["returncode"], "evidence_sha256": _hash(test)},
        "audit": "PASS" if test["returncode"] == 0 else "FAIL",
    }


def verify_execution_evidence(evidence, approved, task, state, workspace):
    if task.operation == "dsh.task.run":
        try:
            return verify_dsh_evidence(evidence, approved, task, state)
        except DshError as exc:
            raise Denied("evidence_integrity") from exc
    """Re-read actual HEAD/file and independently rerun the fixed non-repo check."""
    contract, args = approved["contract"], task.arguments
    if (workspace.binding() != task.workspace or workspace.head() != contract["head"]
            or state["phase"] not in {"COMPLETED", "FAILED"}
            or not re.fullmatch(r"[0-9a-f]{32}", state["attempt_id"] or "")
            or type(state["epoch"]) is not int or state["epoch"] < 1):
        raise Denied("evidence_scope")
    after = workspace.execute("files.read", {"path": args["path"]})["sha256"]
    test = workspace.execute("test.run", {"command_id": contract["test_id"]})
    times = evidence["dispatched_at"], evidence["finished_at"]
    _check_execution_times(approved, times)
    expected = execution_evidence(approved, task, state, args["old_sha256"], after, test, times)
    if (after != digest(args["content"]) or expected != evidence
            or _hash(evidence) != state["evidence_sha256"]
            or (state["phase"] == "COMPLETED") != (test["returncode"] == 0)):
        raise Denied("evidence_integrity")
    return expected


def receipt_envelope(evidence, principal):
    return {"version": 1, "attester": principal, "evidence": evidence, "evidence_sha256": _hash(evidence)}


def verify_receipt(receipt, identities):
    try:
        if type(receipt) is not dict or set(receipt) != {"version", "attester", "evidence", "evidence_sha256", "signature"}:
            raise Denied("receipt_schema")
        unsigned = {key: value for key, value in receipt.items() if key != "signature"}
        principal = unsigned["attester"]
        if (type(unsigned["version"]) is not int or unsigned["version"] != 1 or not _is_id(principal)
                or type(unsigned["evidence"]) is not dict or _hash(unsigned["evidence"]) != unsigned["evidence_sha256"]):
            raise Denied("receipt_integrity")
        _verify(identities.get(principal), principal, "attester", RECEIPT_NS, unsigned, receipt["signature"])
        return unsigned["evidence"]
    except (OSError, ValueError, TypeError, RecursionError) as exc:
        raise Denied("receipt_integrity") from exc


def verify_receipt_bundle(receipt, proof, identities):
    """Offline integrity verification. Historical evidence does not authorize another attempt."""
    try:
        evidence = verify_receipt(receipt, identities)
        if type(proof) is not dict or set(proof) != {"task", "grant", "signature", "contract", "test_result"}:
            raise Denied("proof_schema")
        grant, contract, test = (proof[key] for key in ("grant", "contract", "test_result"))
        if (type(grant) is not dict or set(grant) != GRANT
                or type(contract) is not dict or set(contract) != CONTRACT
                or type(test) is not dict or set(test) != {"command_id", "returncode", "output"}):
            raise Denied("proof_schema")
        principal = grant["principal"]
        authority, attester = identities.get(principal), identities.get(receipt["attester"])
        if authority is None or attester is None or authority.public_key == attester.public_key:
            raise Denied("roles_not_separate")
        _verify(authority, principal, "approver", APPROVAL_NS, grant, proof["signature"])
        task = task_from(proof["task"], contract["workspace"])
        args = task.arguments
        approved = {"contract": contract, "principal": principal, "issued_at": grant["issued_at"],
                    "signed_grant_sha256": _hash(
            {"grant": grant, "signature": proof["signature"]})}
        state = {"attempt_id": evidence["attempt_id"], "epoch": evidence["execution_epoch"]}
        times = evidence["dispatched_at"], evidence["finished_at"]
        _check_execution_times(approved, times)
        common = (grant["contract_sha256"] == _hash(contract)
                  and grant["task_sha256"] == task.request_hash
                  and task.mission_id == contract["mission_id"] and principal == contract["approver"]
                  and contract["status"] == "active" and contract["budget_microusd"] == 0
                  and contract["allowed_operations"] in (["repo.apply_patch"], ["dsh.task.run"])
                  and task.operation == contract["allowed_operations"][0]
                  and test["command_id"] == contract["test_id"] and type(test["returncode"]) is int
                  and test["returncode"] in (0, 1)
                  and isinstance(state["attempt_id"], str)
                  and re.fullmatch(r"[0-9a-f]{32}", state["attempt_id"]) is not None
                  and type(state["epoch"]) is int and state["epoch"] >= 1)
        if not common:
            raise Denied("proof_integrity")
        if task.operation == "dsh.task.run":
            try:
                verify_dsh_evidence(evidence, approved, task, state)
            except DshError as exc:
                raise Denied("proof_integrity") from exc
        elif execution_evidence(approved, task, state, args["old_sha256"],
                                digest(args["content"]), test, times) != evidence:
            raise Denied("proof_integrity")
        return evidence
    except (relay.RelayError, OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        raise Denied("proof_integrity") from exc


def serve_one(endpoint, executor, allowed_uid, *, socket_gid=None, on_ready=None):
    """One authenticated local request. Production identity provisioning is external."""
    different_uid = allowed_uid != os.geteuid()
    directory = _trusted_directory(endpoint.parent, (0o710,) if different_uid else (0o700,))
    if different_uid and (type(socket_gid) is not int or socket_gid != directory.st_gid):
        raise Denied("socket_group_unverified")
    if endpoint.name != "write.sock":
        raise Denied("socket_path")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
        listener.bind(str(endpoint))
        identity = endpoint.lstat()
        try:
            if different_uid:
                os.chown(endpoint, -1, socket_gid, follow_symlinks=False)
            endpoint.chmod(0o660 if different_uid else 0o600)
            listener.settimeout(10)
            listener.listen(1)
            if on_ready is not None:
                on_ready()
            connection, _ = listener.accept()
            with connection:
                try:
                    response = executor.accept(connection, allowed_uid)
                except (relay.RelayError, MissionBlocked, OSError, ValueError, RecursionError):
                    response = {"status": "DENIED"}
                connection.settimeout(2)
                connection.sendall(_encoded(response, 16384))
        finally:
            current = endpoint.lstat()
            if stat.S_ISSOCK(current.st_mode) and (current.st_dev, current.st_ino) == (identity.st_dev, identity.st_ino):
                endpoint.unlink()


if __name__ == "__main__":
    raise SystemExit("Production write startup requires a trusted host, CAB admission and cross-UID isolation.")
