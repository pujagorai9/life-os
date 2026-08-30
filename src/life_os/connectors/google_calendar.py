from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CALENDAR_EVENT_SCOPE = "https://www.googleapis.com/auth/calendar.events"


@dataclass(frozen=True)
class CalendarEvent:
    summary: str
    start_at: str
    end_at: str
    timezone: str
    attendee_email: str
    fingerprint: str
    source_message_id: str
    location: str | None = None


class GoogleCalendarConnector:
    """Minimal Google Calendar event connector.

    Authentication material is supplied by the caller and is never stored in the
    public repository. The connector requests event access, not broad Calendar
    configuration or sharing access.
    """

    def __init__(self, service: Any) -> None:
        self.service = service

    @classmethod
    def authenticate(
        cls, credentials_path: str | Path, token_path: str | Path
    ) -> "GoogleCalendarConnector":
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError as error:
            raise RuntimeError(
                "Install Life OS with the google-calendar extra before connecting"
            ) from error

        credentials_path = Path(credentials_path)
        token_path = Path(token_path)
        if not credentials_path.is_file():
            raise FileNotFoundError(f"OAuth credentials not found: {credentials_path}")

        credentials = None
        if token_path.is_file():
            credentials = Credentials.from_authorized_user_file(
                str(token_path), [CALENDAR_EVENT_SCOPE]
            )
        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(credentials_path), [CALENDAR_EVENT_SCOPE]
                )
                credentials = flow.run_local_server(port=0)
            cls._write_private_token(token_path, credentials.to_json())

        return cls(build("calendar", "v3", credentials=credentials))

    @staticmethod
    def _write_private_token(token_path: Path, token_json: str) -> None:
        token_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = token_path.with_suffix(f"{token_path.suffix}.tmp")
        temporary.write_text(token_json, encoding="utf-8")
        os.chmod(temporary, 0o600)
        temporary.replace(token_path)

    def verify(self) -> dict[str, Any]:
        """Verify event access without modifying Calendar."""
        result = (
            self.service.events()
            .list(calendarId="primary", maxResults=1, singleEvents=True)
            .execute()
        )
        return {
            "connected": True,
            "calendar": "primary",
            "sample_event_count": len(result.get("items", [])),
        }

    def find_by_fingerprint(self, fingerprint: str) -> dict[str, Any] | None:
        result = (
            self.service.events()
            .list(
                calendarId="primary",
                privateExtendedProperty=f"life_os_fingerprint={fingerprint}",
                maxResults=2,
                singleEvents=True,
            )
            .execute()
        )
        events = result.get("items", [])
        if len(events) > 1:
            raise RuntimeError("Multiple Calendar events share this Life OS fingerprint")
        return events[0] if events else None

    def create_event(self, event: CalendarEvent) -> dict[str, Any]:
        existing = self.find_by_fingerprint(event.fingerprint)
        if existing:
            return existing
        return (
            self.service.events()
            .insert(
                calendarId="primary",
                sendUpdates="all",
                body=self._event_body(event),
            )
            .execute()
        )

    def update_event(self, event_id: str, event: CalendarEvent) -> dict[str, Any]:
        return (
            self.service.events()
            .update(
                calendarId="primary",
                eventId=event_id,
                sendUpdates="all",
                body=self._event_body(event),
            )
            .execute()
        )

    def delete_event(self, event_id: str) -> None:
        (
            self.service.events()
            .delete(calendarId="primary", eventId=event_id, sendUpdates="all")
            .execute()
        )

    @staticmethod
    def _event_body(event: CalendarEvent) -> dict[str, Any]:
        body: dict[str, Any] = {
            "summary": event.summary,
            "start": {"dateTime": event.start_at, "timeZone": event.timezone},
            "end": {"dateTime": event.end_at, "timeZone": event.timezone},
            "attendees": [{"email": event.attendee_email}],
            "extendedProperties": {
                "private": {
                    "life_os_fingerprint": event.fingerprint,
                    "life_os_source_message_id": event.source_message_id,
                }
            },
        }
        if event.location:
            body["location"] = event.location
        return body


def redact_token_file(token_path: str | Path) -> dict[str, Any]:
    """Return non-secret token metadata for diagnostics."""
    data = json.loads(Path(token_path).read_text(encoding="utf-8"))
    return {
        "has_refresh_token": bool(data.get("refresh_token")),
        "scopes": data.get("scopes", []),
        "token_type": "authorized_user" if data.get("client_id") else "unknown",
    }
