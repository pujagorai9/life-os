from __future__ import annotations

import json
import os
import secrets
import time
from dataclasses import dataclass
from datetime import date, datetime, time as datetime_time, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx


WHOOP_AUTHORIZE_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
WHOOP_TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
WHOOP_API_ROOT = "https://api.prod.whoop.com/developer/v2"
WHOOP_SCOPES = (
    "offline",
    "read:cycles",
    "read:recovery",
    "read:sleep",
    "read:workout",
)


@dataclass(frozen=True)
class WhoopAuthorization:
    url: str
    state: str


class WhoopConnector:
    """Private WHOOP OAuth connector with rotating refresh-token support."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        token_path: str | Path,
        client: httpx.Client | None = None,
    ) -> None:
        if not client_id or not client_secret:
            raise ValueError("WHOOP client credentials are not configured")
        if not redirect_uri.startswith("https://"):
            raise ValueError("WHOOP_REDIRECT_URI must use HTTPS")
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.token_path = Path(token_path)
        self.state_path = self.token_path.with_name("whoop-oauth-state.json")
        self.client = client or httpx.Client(timeout=30)

    @classmethod
    def from_environment(cls) -> "WhoopConnector":
        return cls(
            client_id=os.getenv("WHOOP_CLIENT_ID", "").strip(),
            client_secret=os.getenv("WHOOP_CLIENT_SECRET", "").strip(),
            redirect_uri=os.getenv("WHOOP_REDIRECT_URI", "").strip(),
            token_path=os.getenv(
                "WHOOP_TOKEN_PATH", "private/whoop-token.json"
            ).strip(),
        )

    def begin_authorization(self) -> WhoopAuthorization:
        state = secrets.token_hex(16)
        self._write_private_json(
            self.state_path,
            {"state": state, "issued_at": int(time.time())},
        )
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "scope": " ".join(WHOOP_SCOPES),
                "state": state,
            }
        )
        return WhoopAuthorization(url=f"{WHOOP_AUTHORIZE_URL}?{query}", state=state)

    def exchange_code(self, code: str, returned_state: str) -> dict[str, Any]:
        self._consume_state(returned_state)
        response = self.client.post(
            WHOOP_TOKEN_URL,
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
        if token is None:
            if not self.token_path.is_file():
                return {
                    "configured": True,
                    "connected": False,
                    "scope": [],
                    "has_refresh_token": False,
                }
            token = self._read_token()
        return {
            "configured": True,
            "connected": bool(token.get("access_token")),
            "scope": sorted(str(token.get("scope", "")).split()),
            "has_refresh_token": bool(token.get("refresh_token")),
        }

    def daily_data(
        self, start_date: date, end_date: date
    ) -> dict[str, list[dict[str, Any]]]:
        token = self._valid_token()
        headers = {"Authorization": f"Bearer {token['access_token']}"}
        start = datetime.combine(
            start_date, datetime_time.min, tzinfo=timezone.utc
        ).isoformat()
        end = datetime.combine(
            end_date + timedelta(days=1), datetime_time.min, tzinfo=timezone.utc
        ).isoformat()
        return {
            "cycles": self._collection("cycle", headers, start, end),
            "recoveries": self._collection("recovery", headers, start, end),
            "sleeps": self._collection("activity/sleep", headers, start, end),
            "workouts": self._collection("activity/workout", headers, start, end),
        }

    def _collection(
        self,
        path: str,
        headers: dict[str, str],
        start: str,
        end: str,
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        next_token: str | None = None
        while True:
            params: dict[str, str | int] = {
                "limit": 25,
                "start": start,
                "end": end,
            }
            if next_token:
                params["nextToken"] = next_token
            response = self.client.get(
                f"{WHOOP_API_ROOT}/{path}", headers=headers, params=params
            )
            response.raise_for_status()
            payload = response.json()
            records.extend(payload.get("records", []))
            next_token = payload.get("next_token")
            if not next_token:
                return records

    def _valid_token(self) -> dict[str, Any]:
        token = self._read_token()
        received_at = int(token.get("received_at", 0))
        expires_in = int(token.get("expires_in", 0))
        if received_at + expires_in - 60 > int(time.time()):
            return token
        refresh_token = token.get("refresh_token")
        if not refresh_token:
            raise RuntimeError("WHOOP authorization has expired; reconnect WHOOP")
        response = self.client.post(
            WHOOP_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": " ".join(WHOOP_SCOPES),
            },
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        refreshed = response.json()
        refreshed["received_at"] = int(time.time())
        self._write_token(refreshed)
        return refreshed

    def _consume_state(self, returned_state: str) -> None:
        if not self.state_path.is_file():
            raise RuntimeError("WHOOP authorization state is missing or expired")
        pending = json.loads(self.state_path.read_text(encoding="utf-8"))
        expected = str(pending.get("state", ""))
        issued_at = int(pending.get("issued_at", 0))
        if int(time.time()) - issued_at > 600:
            self.state_path.unlink(missing_ok=True)
            raise RuntimeError("WHOOP authorization state has expired")
        if not expected or not secrets.compare_digest(returned_state, expected):
            raise RuntimeError("WHOOP authorization state did not match")
        self.state_path.unlink(missing_ok=True)

    def _read_token(self) -> dict[str, Any]:
        if not self.token_path.is_file():
            raise RuntimeError("WHOOP is not connected")
        return json.loads(self.token_path.read_text(encoding="utf-8"))

    def _write_token(self, token: dict[str, Any]) -> None:
        self._write_private_json(self.token_path, token)

    @staticmethod
    def _write_private_json(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(f"{path.suffix}.tmp")
        temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
        os.chmod(temporary, 0o600)
        temporary.replace(path)
