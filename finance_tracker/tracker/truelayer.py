import json
import urllib.parse
import urllib.request
from datetime import timedelta

from django.conf import settings
from django.utils import timezone


def auth_base():
    return "https://auth.truelayer-sandbox.com" if settings.TRUELAYER_ENV == "sandbox" else "https://auth.truelayer.com"


def api_base():
    return "https://api.truelayer-sandbox.com" if settings.TRUELAYER_ENV == "sandbox" else "https://api.truelayer.com"


def build_auth_url(state: str) -> str:
    query = urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": settings.TRUELAYER_CLIENT_ID,
            "redirect_uri": settings.TRUELAYER_REDIRECT_URI,
            "scope": "info accounts balance transactions offline_access",
            "state": state,
        }
    )
    return f"{auth_base()}/?{query}"


def exchange_code(code: str) -> dict:
    return _token_request(
        {
            "grant_type": "authorization_code",
            "client_id": settings.TRUELAYER_CLIENT_ID,
            "client_secret": settings.TRUELAYER_CLIENT_SECRET,
            "redirect_uri": settings.TRUELAYER_REDIRECT_URI,
            "code": code,
        }
    )


def refresh_access_token(refresh_token: str) -> dict:
    return _token_request(
        {
            "grant_type": "refresh_token",
            "client_id": settings.TRUELAYER_CLIENT_ID,
            "client_secret": settings.TRUELAYER_CLIENT_SECRET,
            "refresh_token": refresh_token,
        }
    )


def token_expires_at(expires_in: int):
    return timezone.now() + timedelta(seconds=expires_in)


def api_get(path: str, access_token: str) -> dict:
    url = f"{api_base()}{path}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {access_token}")
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _token_request(payload: dict) -> dict:
    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(f"{auth_base()}/connect/token", data=data)
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))
