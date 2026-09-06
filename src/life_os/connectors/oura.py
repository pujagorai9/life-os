from __future__ import annotations

import json
import os
import secrets
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx


OURA_AUTHORIZE_URL = "https://cloud.ouraring.com/oauth/authorize"
OURA_TOKEN_URL = "https://api.ouraring.com/oauth/token"
OURA_API_ROOT = "https://api.ouraring.com/v2/usercollection"
OURA_SCOPES = ("daily",)


@dataclass(frozen=True)
class OuraAuthorization:
    url: str
    state: str


class OuraConnector:
    """Least-privilege Oura OAuth and daily-summary connector.

    Client credentials and tokens are supplied by the private runtime. They are
    never embedded in the public project or included in diagnostic output.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        token_path: str | Path,
        client: httpx.Client | None = None,
    ) -> None:
        if not client_id or not client_secret:
            raise ValueError("Oura client credentials are not configured")
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.token_path = Path(token_path)
        self.client = client or httpx.Client(timeout=30)

    @classmethod
    def from_environment(cls) -> "OuraConnector":
        return cls(
            client_id=os.getenv("OURA_CLIENT_ID", "").strip(),
            client_secret=os.getenv("OURA_CLIENT_SECRET", "").strip(),
            redirect_uri=os.getenv(
                "OURA_REDIRECT_URI", "http://localhost:8765/callback"
            ).strip(),
            token_path=os.getenv("OURA_TOKEN_PATH", "private/oura-token.json").strip(),
        )

    def begin_authorization(self) -> OuraAuthorization:
        state = secrets.token_urlsafe(32)
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "scope": " ".join(OURA_SCOPES),
                "state": state,
            }
        )
        return OuraAuthorization(url=f"{OURA_AUTHORIZE_URL}?{query}", state=state)

    def exchange_code(self, code: str) -> dict[str, Any]:
        response = self.client.post(
            OURA_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        token = response.json()
        token["received_at"] = int(time.time())
        self._write_token(token)
        return self.token_status(token)

    def token_status(self, token: dict[str, Any] | None = None) -> dict[str, Any]:
        token = token or self._read_token()
        return {
            "connected": bool(token.get("access_token")),
            "scope": sorted(str(token.get("scope", "")).split()),
            "has_refresh_token": bool(token.get("refresh_token")),
            "expires_in": token.get("expires_in"),
        }

    def daily_summaries(
        self, start_date: date, end_date: date
    ) -> dict[str, list[dict[str, Any]]]:
        token = self._valid_token()
        headers = {"Authorization": f"Bearer {token['access_token']}"}
        params = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }
        summaries: dict[str, list[dict[str, Any]]] = {}
        for name in ("daily_sleep", "daily_readiness", "daily_activity", "sleep"):
            response = self.client.get(
                f"{OURA_API_ROOT}/{name}", headers=headers, params=params
            )
            response.raise_for_status()
            summaries[name] = response.json().get("data", [])
        return summaries

    def _valid_token(self) -> dict[str, Any]:
        token = self._read_token()
        received_at = int(token.get("received_at", 0))
        expires_in = int(token.get("expires_in", 0))
        if received_at + expires_in - 60 > int(time.time()):
            return token
        refresh_token = token.get("refresh_token")
        if not refresh_token:
            raise RuntimeError("Oura authorization has expired; reconnect Oura")
        response = self.client.post(
            OURA_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        refreshed = response.json()
        refreshed["received_at"] = int(time.time())
        self._write_token(refreshed)
        return refreshed

    def _read_token(self) -> dict[str, Any]:
        if not self.token_path.is_file():
            raise RuntimeError("Oura is not connected")
        return json.loads(self.token_path.read_text(encoding="utf-8"))

    def _write_token(self, token: dict[str, Any]) -> None:
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.token_path.with_suffix(f"{self.token_path.suffix}.tmp")
        temporary.write_text(json.dumps(token, indent=2), encoding="utf-8")
        os.chmod(temporary, 0o600)
        temporary.replace(self.token_path)
