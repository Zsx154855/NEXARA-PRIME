"""Offline-only route verification for the P3 `dsh.task.run` operation.

Verified BEFORE any adapter runs: a route label returned after execution cannot undo a
paid call. Only loopback HTTP and local unix sockets are accepted, billable credentials
must be absent from the environment, and the endpoint must answer a real probe.
"""
from __future__ import annotations

import datetime as dt
import os
import socket
from urllib.parse import urlsplit

LOCAL_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})
BILLABLE_ENV = ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY",
                "AZURE_OPENAI_API_KEY", "MISTRAL_API_KEY")
KINDS = frozenset({"loopback-http", "unix-socket"})


class RouteError(Exception):
    pass


def _probe_tcp(host, port, timeout=2.0):
    with socket.create_connection((host, port), timeout=timeout):
        return "connected"


def _probe_unix(path, timeout=2.0):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(timeout)
        client.connect(path)
        return "connected"


def _parse(route):
    if not isinstance(route, dict) or set(route) != {"kind", "endpoint"}:
        raise RouteError("route_schema")
    kind, endpoint = route["kind"], route["endpoint"]
    if kind not in KINDS or not isinstance(endpoint, str) or not endpoint:
        raise RouteError("route_schema")
    if kind == "unix-socket":
        if not endpoint.startswith("/") or ".." in endpoint:
            raise RouteError("route_schema")
        return kind, {"path": endpoint}
    parts = urlsplit(endpoint)
    if parts.scheme != "http" or not parts.hostname or parts.hostname not in LOCAL_HOSTS:
        raise RouteError("egress_denied")
    port = parts.port or 80
    if not 1 <= port <= 65535:
        raise RouteError("route_schema")
    if parts.query or parts.fragment:
        raise RouteError("route_schema")
    return kind, {"host": parts.hostname, "port": port, "path": parts.path or "/"}


def verify_route(route, *, prober=None, environ=None):
    """Return a proof dict, or raise RouteError before any adapter is allowed to run."""
    kind, target = _parse(route)
    env = os.environ if environ is None else environ
    present = [name for name in BILLABLE_ENV if env.get(name)]
    if present:
        raise RouteError("billable_credential_present")
    probe = prober or (_probe_unix if kind == "unix-socket" else _probe_tcp)
    try:
        if kind == "unix-socket":
            state = probe(target["path"])
        else:
            state = probe(target["host"], target["port"])
    except (OSError, ValueError) as exc:
        raise RouteError("route_unverified") from exc
    if state != "connected":
        raise RouteError("route_unverified")
    return {
        "route_kind": kind,
        "route_endpoint": route["endpoint"],
        "probe": state,
        "billable": False,
        "verified_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "billable_env_present": False,
    }
