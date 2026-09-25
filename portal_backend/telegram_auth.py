from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl


class TelegramAuthError(ValueError):
    pass


@dataclass(frozen=True)
class TelegramIdentity:
    user_id: str
    display_name: str
    username: str | None
    auth_date: int
    raw_user: dict[str, Any]


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise TelegramAuthError(code)


def validate_mini_app_init_data(
    init_data: str,
    *,
    bot_token: str,
    max_age_seconds: int = 600,
    now: int | None = None,
) -> TelegramIdentity:
    _require(bool(init_data), "TELEGRAM_INIT_DATA_REQUIRED")
    _require(bool(bot_token), "TELEGRAM_BOT_TOKEN_REQUIRED")
    pairs = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
    supplied_hash = pairs.pop("hash", None)
    _require(bool(supplied_hash), "TELEGRAM_HASH_REQUIRED")

    data_check = "\n".join(f"{key}={pairs[key]}" for key in sorted(pairs))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    expected = hmac.new(secret_key, data_check.encode("utf-8"), hashlib.sha256).hexdigest()
    _require(hmac.compare_digest(expected, str(supplied_hash)), "TELEGRAM_HASH_INVALID")

    auth_date = int(pairs.get("auth_date") or 0)
    current = int(time.time()) if now is None else int(now)
    _require(auth_date > 0, "TELEGRAM_AUTH_DATE_REQUIRED")
    _require(auth_date <= current + 30, "TELEGRAM_AUTH_DATE_IN_FUTURE")
    _require(current - auth_date <= int(max_age_seconds), "TELEGRAM_INIT_DATA_EXPIRED")

    try:
        user = json.loads(pairs.get("user") or "{}")
    except json.JSONDecodeError as exc:
        raise TelegramAuthError("TELEGRAM_USER_JSON_INVALID") from exc
    _require(isinstance(user, dict), "TELEGRAM_USER_REQUIRED")
    uid = str(user.get("id") or "")
    _require(uid.isdigit(), "TELEGRAM_USER_ID_INVALID")
    _require(user.get("is_bot") is not True, "TELEGRAM_BOT_CANNOT_LOGIN_AS_HUMAN")

    first = str(user.get("first_name") or "").strip()
    last = str(user.get("last_name") or "").strip()
    display = " ".join(x for x in (first, last) if x).strip() or f"Telegram {uid}"
    username = str(user.get("username") or "").strip() or None
    return TelegramIdentity(
        user_id=uid,
        display_name=display[:120],
        username=username,
        auth_date=auth_date,
        raw_user=user,
    )


def telegram_oidc_metadata() -> dict[str, Any]:
    return {
        "issuer": "https://oauth.telegram.org",
        "discovery": "https://oauth.telegram.org/.well-known/openid-configuration",
        "authorization_endpoint": "https://oauth.telegram.org/auth",
        "token_endpoint": "https://oauth.telegram.org/token",
        "jwks_uri": "https://oauth.telegram.org/.well-known/jwks.json",
        "response_type": "code",
        "pkce": "S256_REQUIRED_BY_JANUS_POLICY",
        "scopes": ["openid", "profile", "telegram:bot_access"],
        "userinfo_endpoint": None,
        "id_token_validation": [
            "VERIFY_JWKS_SIGNATURE",
            "iss == https://oauth.telegram.org",
            "aud == configured BotFather client_id",
            "exp > now",
            "state bound to login attempt",
            "PKCE verifier matches challenge",
        ],
    }
