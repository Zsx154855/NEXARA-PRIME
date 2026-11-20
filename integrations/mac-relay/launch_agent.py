"""Stage a disabled per-user LaunchAgent or remove this relay's registered job."""

import argparse
import grp
import os
from pathlib import Path
import plistlib
import pwd
import stat
import subprocess
import sys

import relay


LABEL = "com.nexara.durable-relay"
ROOT = Path(__file__).resolve().parent
LAUNCHCTL = "/bin/launchctl"


def definition(config):
    return {
        "Label": LABEL,
        "ProgramArguments": ["/usr/bin/env", "-i", str(Path(sys.executable).resolve()),
                             "-E", "-s", "-B", str(ROOT / "durable.py"),
                             "--config", str(config), "--foreground"],
        "WorkingDirectory": str(ROOT),
        "RunAtLoad": True,
        "KeepAlive": {"SuccessfulExit": False},
        "ThrottleInterval": 60,
        "ExitTimeOut": 45,
        "LimitLoadToSessionType": "Aqua",
        "Nice": 10,
        "Umask": 0o077,
        "SoftResourceLimits": {"NumberOfFiles": 64},
        "HardResourceLimits": {"NumberOfFiles": 64},
        "StandardOutPath": "/dev/null",
        "StandardErrorPath": "/dev/null",
    }


def launchctl(*arguments):
    return subprocess.run([LAUNCHCTL, *arguments], stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, timeout=15).returncode


def admin_identity():
    identity = pwd.getpwuid(os.getuid())
    return grp.getgrnam("admin").gr_gid in os.getgrouplist(identity.pw_name, identity.pw_gid)


def status(target, installed):
    active = launchctl("print", target) == 0
    return active, os.path.lexists(installed)


def stage(config):
    draft = config.parent / (LABEL + ".plist.disabled")
    fd = os.open(draft, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as handle:
        plistlib.dump(definition(config), handle)
        handle.flush()
        os.fsync(handle.fileno())
    return draft


def uninstall(config, target, installed):
    exists = os.path.lexists(installed)
    if exists:
        info = installed.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise relay.RelayError("unknown_installed_plist")
        with installed.open("rb") as file:
            if plistlib.load(file) != definition(config):
                raise relay.RelayError("unknown_installed_plist")
    active, present = status(target, installed)
    if not active and not present:
        return "ALREADY_UNINSTALLED"
    if active and not exists:
        raise relay.RelayError("unknown_registered_job")
    fd = os.open(config.parent / "STOP", os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    os.close(fd)
    if launchctl("print", target) == 0:
        launchctl("bootout", target)
        if launchctl("print", target) == 0:
            raise relay.RelayError("bootout_unverified")
    if exists:
        installed.unlink()
    return "UNINSTALLED_LEDGER_PRESERVED"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["prepare", "install", "status", "uninstall"])
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        if sys.platform != "darwin" or os.getuid() == 0:
            raise relay.RelayError("requires_macos_nonroot_user")
        config = args.config.absolute()
        relay.load_config(config)
        target = f"gui/{os.getuid()}/{LABEL}"
        installed = Path.home() / "Library" / "LaunchAgents" / (LABEL + ".plist")
        if args.operation == "install":
            if admin_identity():
                raise relay.RelayError("ADMIN_IDENTITY_FORBIDDEN")
            raise relay.RelayError("CREDENTIAL_BOUNDARY_AND_CROSS_UID_ACCESS_NOT_VERIFIED")
        if args.operation == "prepare":
            stage(config)
            print("DISABLED_PLIST_PREPARED")
        elif args.operation == "uninstall":
            print(uninstall(config, target, installed))
        else:
            active, present = status(target, installed)
            print(f"registered={str(active).lower()} plist_present={str(present).lower()}")
        return 0
    except (relay.RelayError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print("LAUNCH_AGENT_BLOCKED=" + (str(exc) if isinstance(exc, relay.RelayError) else type(exc).__name__))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
