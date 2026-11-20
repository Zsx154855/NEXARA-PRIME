"""Freeze a private P3 ledger without rolling back unknown writes."""

import argparse
import os
from pathlib import Path
import stat

from durable import stopped
from p3_private import PrivateMissionController
import relay


def freeze(folder):
    info = folder.lstat()
    if (folder != folder.resolve() or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o700
            or any(os.path.lexists(folder / name) for name in
                   ("durable.sqlite3", "state.json", "p2-missions.sqlite3"))):
        raise relay.RelayError("private_p3_ledger_required")
    db = (folder / PrivateMissionController.database_name).lstat()
    if (not stat.S_ISREG(db.st_mode) or db.st_uid != os.geteuid() or db.st_nlink != 1
            or stat.S_IMODE(db.st_mode) != 0o600):
        raise relay.RelayError("private_p3_ledger_required")
    if not stopped(folder):
        fd = os.open(folder / "STOP", os.O_WRONLY | os.O_NOFOLLOW | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        directory = os.open(folder, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    return "ADMISSION_FROZEN_LEDGER_AND_FILES_PRESERVED"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(freeze(args.ledger.absolute()))
    except (OSError, relay.RelayError):
        print("P3_FREEZE_BLOCKED")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
