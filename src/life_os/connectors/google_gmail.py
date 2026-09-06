from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


GMAIL_READ_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"


class GoogleGmailConnector:
    """Least-privilege Gmail reader for one explicitly authorized household member."""

    def __init__(self, service: Any) -> None:
        self.service = service

    @classmethod
    def authenticate(
        cls,
        credentials_path: str | Path,
        token_path: str | Path,
        *,
        open_browser: bool = True,
    ) -> "GoogleGmailConnector":
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError as error:
            raise RuntimeError(
                "Install Life OS with the google-gmail extra before connecting Gmail"
            ) from error

        credentials_path = Path(credentials_path)
        token_path = Path(token_path)
        if not credentials_path.is_file():
            raise FileNotFoundError(f"OAuth credentials not found: {credentials_path}")

        credentials = None
        if token_path.is_file():
            credentials = Credentials.from_authorized_user_file(
                str(token_path), [GMAIL_READ_SCOPE]
            )
        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(credentials_path), [GMAIL_READ_SCOPE]
                )
                credentials = flow.run_local_server(
                    port=0,
                    open_browser=open_browser,
                    prompt="consent select_account",
                    access_type="offline",
                )
            cls._write_private_json(token_path, credentials.to_json())

        return cls(build("gmail", "v1", credentials=credentials))

    def profile(self) -> dict[str, Any]:
        profile = self.service.users().getProfile(userId="me").execute()
        return {
            "connected": True,
            "email": str(profile.get("emailAddress", "")).strip().lower(),
            "messages_total": int(profile.get("messagesTotal", 0)),
        }

    @staticmethod
    def _write_private_json(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(f"{path.suffix}.tmp")
        temporary.write_text(content, encoding="utf-8")
        os.chmod(temporary, 0o600)
        temporary.replace(path)


def safe_account_id(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9_-]+", "-", value.strip().lower()).strip("-")
    if not normalized or len(normalized) > 60:
        raise ValueError("account id must contain letters or numbers and be under 60 characters")
    return normalized


def register_gmail_account(
    registry_path: str | Path,
    *,
    account_id: str,
    email: str,
    member_name: str,
    token_path: str | Path,
) -> dict[str, Any]:
    registry_path = Path(registry_path)
    account_id = safe_account_id(account_id)
    registry: dict[str, Any] = {"accounts": []}
    if registry_path.is_file():
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    accounts = [
        item
        for item in registry.get("accounts", [])
        if item.get("account_id") != account_id and item.get("email") != email
    ]
    record = {
        "account_id": account_id,
        "email": email.strip().lower(),
        "member_name": member_name.strip(),
        "token_file": Path(token_path).name,
        "connected_at": datetime.now(timezone.utc).isoformat(),
        "scopes": [GMAIL_READ_SCOPE],
    }
    accounts.append(record)
    registry["accounts"] = sorted(accounts, key=lambda item: item["member_name"].casefold())
    GoogleGmailConnector._write_private_json(
        registry_path, json.dumps(registry, indent=2)
    )
    return record


def list_gmail_accounts(registry_path: str | Path) -> list[dict[str, Any]]:
    path = Path(registry_path)
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        {
            "account_id": item["account_id"],
            "email": item["email"],
            "member_name": item["member_name"],
            "connected_at": item["connected_at"],
            "scopes": item.get("scopes", []),
        }
        for item in data.get("accounts", [])
    ]
