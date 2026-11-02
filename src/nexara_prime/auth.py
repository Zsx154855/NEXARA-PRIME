"""Accounts and sessions for the optional multi-tenant profile.

The default deployment stays single-owner and never touches this module. When
``NEXARA_MULTI_TENANT=1`` the API requires a session cookie and every record is
written under the account's tenant id (enforced in ``db.py``).
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

SCRYPT_N, SCRYPT_R, SCRYPT_P = 2 ** 14, 8, 1
SESSION_DAYS = 7
COOKIE_NAME = "nx_session"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt,
                            n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
    return f"scrypt${salt.hex()}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    if scheme != "scrypt":
        return False
    candidate = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt_hex),
                               n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
    return hmac.compare_digest(candidate.hex(), digest_hex)


def tenant_for(email: str) -> str:
    return "t_" + hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()[:12]


class AuthService:
    def __init__(self, store):
        self.store = store
        self._init_schema()

    def _init_schema(self) -> None:
        with self.store._lock, self.store._conn:
            self.store._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'owner',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );
                """
            )
            columns = {row["name"] for row in self.store._conn.execute("PRAGMA table_info(users)")}
            if "role" not in columns:
                self.store._conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'member'")

    # -- users -----------------------------------------------------------
    def signup(self, email: str, password: str) -> dict:
        email = email.strip().lower()
        if "@" not in email or len(email) > 254:
            raise ValueError("invalid_email")
        if len(password) < 8:
            raise ValueError("password_too_short")
        tenant = tenant_for(email)
        user_id = "usr_" + secrets.token_hex(8)
        with self.store._lock, self.store._conn:
            self.store._conn.execute(
                "INSERT INTO users(user_id, email, password_hash, tenant_id, role, created_at) VALUES (?,?,?,?,?,?)",
                (user_id, email, _hash_password(password), tenant, "owner", _now().isoformat()),
            )
        return {"user_id": user_id, "email": email, "tenant_id": tenant, "role": "owner"}

    def invite(self, owner: dict, email: str, password: str) -> dict:
        """Add a member to the owner's tenant. Owner-only (checked by the route)."""
        email = email.strip().lower()
        if "@" not in email or len(email) > 254:
            raise ValueError("invalid_email")
        if len(password) < 8:
            raise ValueError("password_too_short")
        user_id = "usr_" + secrets.token_hex(8)
        with self.store._lock, self.store._conn:
            self.store._conn.execute(
                "INSERT INTO users(user_id, email, password_hash, tenant_id, role, created_at) VALUES (?,?,?,?,?,?)",
                (user_id, email, _hash_password(password), owner["tenant_id"], "member", _now().isoformat()),
            )
        return {"user_id": user_id, "email": email, "tenant_id": owner["tenant_id"], "role": "member"}

    def authenticate(self, email: str, password: str) -> dict | None:
        email = email.strip().lower()
        with self.store._lock:
            row = self.store._conn.execute(
                "SELECT user_id, email, password_hash, tenant_id, role FROM users WHERE email=?",
                (email,),
            ).fetchone()
        if not row or not _verify_password(password, row["password_hash"]):
            return None
        return {"user_id": row["user_id"], "email": row["email"],
                "tenant_id": row["tenant_id"], "role": row["role"]}

    # -- sessions --------------------------------------------------------
    def issue(self, user: dict) -> str:
        token = secrets.token_urlsafe(32)
        expires = (_now() + timedelta(days=SESSION_DAYS)).isoformat()
        with self.store._lock, self.store._conn:
            self.store._conn.execute(
                "INSERT INTO sessions(token_hash, user_id, tenant_id, created_at, expires_at) VALUES (?,?,?,?,?)",
                (hashlib.sha256(token.encode()).hexdigest(), user["user_id"], user["tenant_id"],
                 _now().isoformat(), expires),
            )
        return token

    def resolve(self, token: str) -> dict | None:
        if not token:
            return None
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self.store._lock:
            row = self.store._conn.execute(
                "SELECT s.user_id, s.tenant_id, s.expires_at, u.email, u.role FROM sessions s "
                "JOIN users u ON u.user_id = s.user_id WHERE s.token_hash=?",
                (digest,),
            ).fetchone()
        if not row:
            return None
        if datetime.fromisoformat(row["expires_at"]) <= _now():
            return None
        return {"user_id": row["user_id"], "tenant_id": row["tenant_id"],
                "email": row["email"], "role": row["role"]}

    def revoke(self, token: str) -> None:
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self.store._lock, self.store._conn:
            self.store._conn.execute("DELETE FROM sessions WHERE token_hash=?", (digest,))
