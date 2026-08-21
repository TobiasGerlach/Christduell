import hashlib
from datetime import timedelta

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings
from app.core.time import utcnow

ALGORITHM = "HS256"

_password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _password_hash.verify(password, password_hash)


def create_access_token(player_id: int) -> str:
    settings = get_settings()
    issued_at = utcnow()
    payload = {
        "sub": str(player_id),
        "iat": issued_at,
        "exp": issued_at + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> int | None:
    """Returns the player id encoded in the token, or None if it is invalid."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None

    subject = payload.get("sub")
    if subject is None:
        return None
    try:
        return int(subject)
    except (TypeError, ValueError):
        return None


# --- Password reset tokens -------------------------------------------------
# Stateless single-use: the token carries a fingerprint of the *current*
# password hash. Once the password changes the fingerprint no longer matches,
# so a used (or outdated) token dies without any server-side bookkeeping.

RESET_TOKEN_EXPIRE_MINUTES = 60


def _hash_fingerprint(password_hash: str | None) -> str:
    return hashlib.sha256((password_hash or "none").encode()).hexdigest()[:16]


def create_password_reset_token(player_id: int, password_hash: str | None) -> str:
    settings = get_settings()
    issued_at = utcnow()
    payload = {
        "sub": str(player_id),
        "typ": "pwreset",
        "fph": _hash_fingerprint(password_hash),
        "iat": issued_at,
        "exp": issued_at + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_password_reset_token(token: str, current_password_hash_lookup) -> int | None:
    """Returns the player id, or None if invalid/expired/already used.

    `current_password_hash_lookup(player_id) -> str | None` fetches the hash to
    check the single-use fingerprint against.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("typ") != "pwreset":
        return None
    try:
        player_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        return None
    if payload.get("fph") != _hash_fingerprint(current_password_hash_lookup(player_id)):
        return None
    return player_id
