"""External condition watcher — detects when WAIT_EXTERNAL programs can resume."""
from __future__ import annotations

import threading
import time
from typing import Any, Protocol

from nexara_prime.events import EventBus


class ConditionCheckFn(Protocol):
    """A callable that checks if an external condition is satisfied."""
    def __call__(self, condition_ref: str) -> bool: ...


class ExternalConditionWatcher:
    """Watches external conditions and emits events when they're satisfied.

    Supports:
    - GitHub PR review return (Codex threads resolved)
    - CI status changes
    - Approval status changes
    - Worker health changes
    - Timer-based retry
    - Filesystem events (stub)
    - New user directives (polling)

    This is the INTERFACE — real implementations register check functions.
    The default implementation uses local polling; it does NOT depend on
    maintaining an open chat window.
    """

    def __init__(self, events: EventBus, poll_interval: float = 5.0) -> None:
        self._events = events
        self._poll_interval = poll_interval
        self._checkers: dict[str, ConditionCheckFn] = {}
        self._watched: dict[str, dict[str, Any]] = {}
        self._active = False
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def register_checker(
        self, condition_type: str, check_fn: ConditionCheckFn
    ) -> None:
        """Register a checker function for a condition type."""
        self._checkers[condition_type] = check_fn

    def watch(
        self,
        program_id: str,
        condition_type: str,
        external_ref: str,
        check_interval: float = 60.0,
        timeout_seconds: float = 0.0,
    ) -> str:
        """Start watching an external condition.

        Returns a watch_id that can be used to stop watching.
        """
        watch_id = f"watch:{program_id}:{condition_type}:{external_ref}"
        self._watched[watch_id] = {
            "program_id": program_id,
            "condition_type": condition_type,
            "external_ref": external_ref,
            "check_interval": check_interval,
            "timeout_seconds": timeout_seconds,
            "last_checked": 0.0,
            "satisfied": False,
            "started_at": time.monotonic(),
        }
        return watch_id

    def unwatch(self, watch_id: str) -> None:
        self._watched.pop(watch_id, None)

    def start(self) -> None:
        if self._active:
            return
        self._active = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="nexara-watcher"
        )
        self._thread.start()

    def stop(self) -> None:
        self._active = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

    def _run(self) -> None:
        while self._active and not self._stop_event.is_set():
            self._poll()
            self._stop_event.wait(timeout=self._poll_interval)

    def _poll(self) -> None:
        now = time.monotonic()
        for watch_id, info in list(self._watched.items()):
            if info["satisfied"]:
                continue
            # Respect check interval
            if now - info["last_checked"] < info["check_interval"]:
                continue
            # Check timeout
            if info["timeout_seconds"] > 0:
                elapsed = now - info["started_at"]
                if elapsed >= info["timeout_seconds"]:
                    self._events.publish(
                        "external_condition.timeout",
                        info["program_id"],
                        "watcher", "system", watch_id,
                        {
                            "condition_type": info["condition_type"],
                            "external_ref": info["external_ref"],
                            "elapsed_seconds": elapsed,
                        },
                    )
                    continue

            info["last_checked"] = now
            checker = self._checkers.get(info["condition_type"])
            if checker is None:
                continue
            try:
                satisfied = checker(info["external_ref"])
                if satisfied:
                    info["satisfied"] = True
                    self._events.publish(
                        "external_condition.satisfied",
                        info["program_id"],
                        "watcher", "system", watch_id,
                        {
                            "condition_type": info["condition_type"],
                            "external_ref": info["external_ref"],
                        },
                    )
            except Exception:
                pass  # Checker failed — retry next cycle

    def force_check(self, condition_type: str, external_ref: str) -> bool:
        """Force an immediate check. Returns True if satisfied."""
        checker = self._checkers.get(condition_type)
        if checker is None:
            return False
        try:
            return checker(external_ref)
        except Exception:
            return False

    def get_watched(self, program_id: str = "") -> list[dict[str, Any]]:
        result = []
        for watch_id, info in self._watched.items():
            if program_id and info["program_id"] != program_id:
                continue
            result.append(dict(info, watch_id=watch_id))
        return result

    @property
    def active_conditions(self) -> int:
        return sum(1 for w in self._watched.values() if not w["satisfied"])


# ── Built-in checker: GitHub PR review threads ──

def github_codex_review_checker(gh_binary: str = "gh") -> ConditionCheckFn:
    """Check if a GitHub PR has zero unresolved Codex review threads.

    Uses the gh CLI. Returns True when review threads are all resolved.
    """
    def check(pr_number: str) -> bool:
        import subprocess
        try:
            result = subprocess.run(
                [gh_binary, "api", "graphql", "-f", "query="
                 f'query{{repository(owner:"Zsx154855",name:"NEXARA-PRIME")'
                 f'{{pullRequest(number:{pr_number})'
                 f'{{reviewThreads(first:1){{totalCount}}}}}}}}'],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode != 0:
                return False
            import json
            data = json.loads(result.stdout)
            count = data["data"]["repository"]["pullRequest"]["reviewThreads"]["totalCount"]
            # Resolved = total threads exist but all are resolved
            return count == 0 or _all_resolved(pr_number, gh_binary)
        except Exception:
            return False
    return check


def _all_resolved(pr_number: str, gh_binary: str) -> bool:
    import subprocess
    import json
    try:
        result = subprocess.run(
            [gh_binary, "api", "graphql", "-f", "query="
             f'query{{repository(owner:"Zsx154855",name:"NEXARA-PRIME")'
             f'{{pullRequest(number:{pr_number})'
             f'{{reviewThreads(first:100){{nodes{{isResolved}}}}}}}}}}'],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            return False
        data = json.loads(result.stdout)
        nodes = data["data"]["repository"]["pullRequest"]["reviewThreads"]["nodes"]
        return all(n["isResolved"] for n in nodes)
    except Exception:
        return False
