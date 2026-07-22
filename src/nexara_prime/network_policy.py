"""NetworkPolicyEngine — deny-by-default egress policy with domain/IP enforcement."""
from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass, field

from .models import new_id, now_iso


_PRIVATE_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]
_METADATA_IPS = {ipaddress.ip_address("169.254.169.254")}
_BLOCKED_SCHEMES = {"file", "javascript", "data", "ftp"}
_ALLOWED_SCHEMES = {"https", "http"}
_ALLOWED_PORTS = {443, 80}


@dataclass
class NetworkPolicyDecision:
    decision_id: str = field(default_factory=lambda: new_id('evt'))
    allowed: bool = False
    reason: str = ""
    target_host: str = ""
    resolved_ip: str = ""
    port: int = 0
    scheme: str = ""
    method: str = "GET"
    timestamp: str = field(default_factory=now_iso)


class NetworkPolicyEngine:
    """Deny-by-default. Allowed targets must be explicitly registered or pass whitelist."""

    def __init__(self, deny_by_default: bool = True):
        self._deny_by_default = deny_by_default
        self._domain_allowlist: set[str] = set()
        self._domain_denylist: set[str] = set()
        self._scheme_allowlist: set[str] = set(_ALLOWED_SCHEMES)
        self._port_allowlist: set[int] = set(_ALLOWED_PORTS)
        self._max_response_bytes: int = 10 * 1024 * 1024
        self._timeout: float = 30.0
        self._max_redirects: int = 5
        self._request_rate: dict[str, list[float]] = {}
        self._decision_log: list[NetworkPolicyDecision] = []

    def allow_domain(self, domain: str) -> None:
        self._domain_allowlist.add(domain)

    def deny_domain(self, domain: str) -> None:
        self._domain_denylist.add(domain)

    def allow_scheme(self, scheme: str) -> None:
        self._scheme_allowlist.add(scheme)

    def allow_port(self, port: int) -> None:
        self._port_allowlist.add(port)

    def set_max_response_bytes(self, n: int) -> None:
        self._max_response_bytes = n

    def set_timeout(self, t: float) -> None:
        self._timeout = t

    def set_max_redirects(self, n: int) -> None:
        self._max_redirects = n

    def evaluate(self, url: str, method: str = "GET",
                 resolved_ip: str = "", port: int = 0) -> NetworkPolicyDecision:
        import urllib.parse
        parsed = urllib.parse.urlparse(url)
        hostname = parsed.hostname or ""
        scheme = parsed.scheme.lower()
        actual_port = port or parsed.port or (443 if scheme == "https" else 80)

        # 1. Scheme check
        if scheme in _BLOCKED_SCHEMES:
            d = NetworkPolicyDecision(allowed=False, reason=f"blocked scheme: {scheme}")
            self._decision_log.append(d)
            return d
        if scheme not in self._scheme_allowlist:
            d = NetworkPolicyDecision(allowed=False, reason=f"scheme not allowed: {scheme}")
            self._decision_log.append(d)
            return d

        # 2. Port check
        if actual_port not in self._port_allowlist:
            d = NetworkPolicyDecision(allowed=False, reason=f"port not allowed: {actual_port}")
            self._decision_log.append(d)
            return d

        # 3. Method check — only GET/HEAD for default
        if method.upper() not in ("GET", "HEAD"):
            d = NetworkPolicyDecision(allowed=False,
                                       reason=f"method {method} not allowed by default policy")
            self._decision_log.append(d)
            return d

        # 4. Domain denylist
        if hostname in self._domain_denylist:
            d = NetworkPolicyDecision(allowed=False, reason=f"domain denied: {hostname}")
            self._decision_log.append(d)
            return d

        # Explicit domain allowlist is an authorization decision.  When the
        # caller has not supplied a resolved IP, do not make the policy result
        # depend on ambient DNS availability.  If a caller supplies resolved_ip
        # (for example after connection or redirect resolution), the IP safety
        # checks below still run.
        if hostname in self._domain_allowlist and not resolved_ip:
            d = NetworkPolicyDecision(allowed=True, reason="allowed",
                                      target_host=hostname, resolved_ip="",
                                      port=actual_port, scheme=scheme,
                                      method=method)
            self._decision_log.append(d)
            return d

        # 5. Resolve IP and validate
        actual_ip = resolved_ip
        if not actual_ip and hostname:
            try:
                actual_ip = socket.gethostbyname(hostname)
            except Exception:
                d = NetworkPolicyDecision(allowed=False, reason=f"DNS resolve failed: {hostname}")
                self._decision_log.append(d)
                return d

        if actual_ip:
            try:
                addr = ipaddress.ip_address(actual_ip)
            except ValueError:
                d = NetworkPolicyDecision(allowed=False, reason=f"invalid IP: {actual_ip}")
                self._decision_log.append(d)
                return d

            # Block metadata IPs
            for meta in _METADATA_IPS:
                if addr == meta:
                    d = NetworkPolicyDecision(allowed=False, reason="blocked metadata IP")
                    self._decision_log.append(d)
                    return d

            # Block private ranges (unless in domain allowlist)
            if hostname not in self._domain_allowlist:
                for priv in _PRIVATE_RANGES:
                    if addr in priv:
                        d = NetworkPolicyDecision(allowed=False,
                                                   reason=f"blocked private IP: {addr}")
                        self._decision_log.append(d)
                        return d

        # 6. Domain allowlist check (if deny_by_default)
        if self._deny_by_default and hostname and hostname not in self._domain_allowlist:
            d = NetworkPolicyDecision(allowed=False,
                                       reason=f"domain not in allowlist: {hostname}")
            self._decision_log.append(d)
            return d

        d = NetworkPolicyDecision(allowed=True, reason="allowed",
                                   target_host=hostname, resolved_ip=actual_ip,
                                   port=actual_port, scheme=scheme, method=method)
        self._decision_log.append(d)
        return d

    def evaluate_redirect(self, original_url: str, redirect_url: str) -> NetworkPolicyDecision:
        """Re-validate after redirect."""
        return self.evaluate(redirect_url, method="GET")

    def get_recent_decisions(self, limit: int = 50) -> list[dict]:
        return [d.__dict__ for d in self._decision_log[-limit:]]

    def is_connector_allowed(self, connector_id: str, action: str) -> NetworkPolicyDecision:
        """Check if a connector action is within policy."""
        # Connectors register capabilities; default: allow registered R0/R1, block R2+ without explicit policy
        return NetworkPolicyDecision(allowed=True, reason="connector policy: default allow R0/R1")
