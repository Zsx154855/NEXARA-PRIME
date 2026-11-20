"""Offline review for explicit, hash-locked Python wheel candidates."""

import re
from urllib.parse import urlsplit


class InstallPlanDenied(ValueError):
    pass


def distribution(value):
    return re.sub(r"[-_.]+", "-", value.lower())


def audit_wheels(entries):
    if not isinstance(entries, list) or not 1 <= len(entries) <= 32:
        raise InstallPlanDenied("lock_size")
    reviewed = {}
    for entry in entries:
        if (not isinstance(entry, dict) or set(entry) != {"name", "version", "sha256", "url"}
                or not all(isinstance(value, str) and 0 < len(value) <= 512 for value in entry.values())):
            raise InstallPlanDenied("lock_schema")
        name, version, sha = entry["name"], entry["version"], entry["sha256"]
        if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", name)
                or not re.fullmatch(r"[0-9][A-Za-z0-9._+]{0,63}", version)
                or not re.fullmatch(r"[0-9a-f]{64}", sha)):
            raise InstallPlanDenied("unpinned_artifact")
        try:
            url = urlsplit(entry["url"])
        except ValueError as exc:
            raise InstallPlanDenied("artifact_source") from exc
        if (url.scheme != "https" or url.netloc != "files.pythonhosted.org"
                or url.query or url.fragment
                or not re.fullmatch(r"/packages/(?:[A-Za-z0-9]+/){1,4}[A-Za-z0-9_.+\-]+\.whl", url.path)
                or url.geturl() != entry["url"]):
            raise InstallPlanDenied("artifact_source")
        wheel = url.path.rsplit("/", 1)[1].split("-")
        key = distribution(name)
        if len(wheel) not in (5, 6) or (distribution(wheel[0]), wheel[1]) != (key, version):
            raise InstallPlanDenied("artifact_identity")
        if key in reviewed:
            raise InstallPlanDenied("duplicate_distribution")
        reviewed[key] = entry.copy()
    return tuple(reviewed[key] for key in sorted(reviewed))
