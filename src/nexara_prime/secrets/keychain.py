"""macOS Keychain secret backend using /usr/bin/security."""

from __future__ import annotations

import subprocess
import typing as t

if t.TYPE_CHECKING:
    from .base import SecretBackend


_SECURITY = "/usr/bin/security"
_KEYCHAIN_ACCOUNT = "nexara"


class MacOSKeychainSecretStore:
    """SecretBackend implementation backed by the macOS system Keychain.

    All operations delegate to the ``security`` command-line tool.
    Secrets are stored under the account name ``nexara`` and keyed by
    service name.
    """

    # ------------------------------------------------------------------
    # Public API (SecretBackend interface)
    # ------------------------------------------------------------------

    def set(self, name: str, value: str) -> None:
        """Store *value* under *name* in the keychain.

        Creates an entry or updates an existing one (-U flag).
        """
        self._run(
            _SECURITY,
            "add-generic-password",
            "-a",
            _KEYCHAIN_ACCOUNT,
            "-s",
            name,
            "-w",
            value,
            "-U",
        )

    def get(self, name: str) -> str | None:
        """Retrieve the value for *name* from the keychain.

        Returns ``None`` when the entry does not exist.  The raw secret
        value is *never* logged or printed.
        """
        result = self._run(
            _SECURITY,
            "find-generic-password",
            "-a",
            _KEYCHAIN_ACCOUNT,
            "-s",
            name,
            "-w",
            check=False,
        )
        if result.returncode != 0:
            return None
        return result.stdout.rstrip("\n")

    def exists(self, name: str) -> bool:
        """Return ``True`` if an entry for *name* exists in the keychain."""
        result = self._run(
            _SECURITY,
            "find-generic-password",
            "-a",
            _KEYCHAIN_ACCOUNT,
            "-s",
            name,
            check=False,
        )
        return result.returncode == 0

    def delete(self, name: str) -> None:
        """Remove the entry for *name* from the keychain.

        Raises ``RuntimeError`` if the entry does not exist.
        """
        self._run(
            _SECURITY,
            "delete-generic-password",
            "-a",
            _KEYCHAIN_ACCOUNT,
            "-s",
            name,
        )

    def list_names(self) -> list[str]:
        """Return all secret names stored under the ``nexara`` account."""
        result = self._run(
            _SECURITY,
            "dump-keychain",
            check=False,
        )
        if result.returncode != 0:
            return []
        names: list[str] = []
        lines = result.stdout.splitlines()
        for i, line in enumerate(lines):
            # Look for 'acct' lines with nexara account
            if f'"acct"' in line and _KEYCHAIN_ACCOUNT in line:
                # Scan nearby lines for the service name
                for j in range(max(0, i - 3), min(len(lines), i + 3)):
                    if '"svce"' in lines[j]:
                        parts = lines[j].split("=", 1)
                        if len(parts) == 2:
                            raw = parts[1].strip().strip('"')
                            if raw and raw not in names:
                                names.append(raw)
        return names

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _run(
        *args: str,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        """Execute a ``security`` subprocess and return the result.

        Parameters
        ----------
        *args :
            Command and arguments to pass to ``subprocess.run``.
        check :
            When ``True`` (default), raise ``RuntimeError`` on non-zero
            exit; when ``False`` the raw result is returned so callers
            can inspect the exit code.

        Raises
        ------
        RuntimeError
            If *check* is ``True`` and the subprocess exits with a
            non-zero return code, or if the ``security`` binary is
            unreachable.
        """
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            raise RuntimeError(
                f"macOS keychain unavailable — {_SECURITY} not found"
            ) from None
        except OSError as exc:
            raise RuntimeError(
                f"macOS keychain unavailable — {exc}"
            ) from None

        if check and result.returncode != 0:
            raise RuntimeError(
                f"keychain command failed: {' '.join(args)}\n"
                f"stderr: {result.stderr.strip()}"
            )

        return result
