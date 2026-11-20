"""Print a fresh V2 request draft for the repository owner to review and post."""

from datetime import datetime, timedelta, timezone
import uuid

from relay import PROTOCOL, REQUEST_MARKER, json_canonical


def utc_text(moment):
    return moment.isoformat(timespec="seconds").replace("+00:00", "Z")


if __name__ == "__main__":
    issued = datetime.now(timezone.utc).replace(microsecond=0)
    request = {
        "protocol": PROTOCOL,
        "request_id": f"nexara-relay-v2-{issued:%Y%m%d}-{uuid.uuid4().hex}",
        "tool": "nexara_bridge_state",
        "args": {},
        "issued_at": utc_text(issued),
        "expires_at": utc_text(issued + timedelta(minutes=10)),
    }
    print(REQUEST_MARKER)
    print(json_canonical(request))
