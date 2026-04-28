from dataclasses import dataclass
import logging

from fastapi import Header

from app.core.config import settings
from app.core.errors import AuthenticationError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    groups: list[str]
    role: str

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def require_auth(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> AuthContext:
    if not x_api_key:
        logger.warning("auth_failed", extra={"event": "auth_failed", "reason": "missing_api_key"})
        raise AuthenticationError("Missing X-API-Key header")

    admin_keys = _parse_admin_keys(settings.admin_api_keys)
    if x_api_key in admin_keys:
        return AuthContext(user_id="admin", groups=["admin"], role="admin")

    user = _parse_user_keys(settings.user_api_keys).get(x_api_key)
    if user is not None:
        return user

    logger.warning("auth_failed", extra={"event": "auth_failed", "reason": "invalid_api_key"})
    raise AuthenticationError("Invalid API key")


def _parse_admin_keys(raw: str) -> set[str]:
    return {key.strip() for key in raw.split(",") if key.strip()}


def _parse_user_keys(raw: str) -> dict[str, AuthContext]:
    users: dict[str, AuthContext] = {}
    for entry in raw.split(";"):
        if not entry.strip():
            continue
        parts = [part.strip() for part in entry.split(":", 2)]
        if len(parts) < 2 or not parts[0] or not parts[1]:
            continue
        groups = [group.strip() for group in parts[2].split(",") if group.strip()] if len(parts) == 3 else []
        users[parts[0]] = AuthContext(user_id=parts[1], groups=groups, role="user")
    return users
