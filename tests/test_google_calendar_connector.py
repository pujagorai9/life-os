from __future__ import annotations

from life_os.connectors.google_calendar import CalendarEvent, GoogleCalendarConnector


class Request:
    def __init__(self, result=None):
        self.result = result or {}

    def execute(self):
        return self.result


class Events:
    def __init__(self):
        self.calls = []
        self.list_result = {"items": []}

    def list(self, **kwargs):
        self.calls.append(("list", kwargs))
        return Request(self.list_result)

    def insert(self, **kwargs):
        self.calls.append(("insert", kwargs))
        return Request({"id": "event-1"})

    def update(self, **kwargs):
        self.calls.append(("update", kwargs))
        return Request({"id": kwargs["eventId"]})

    def delete(self, **kwargs):
        self.calls.append(("delete", kwargs))
        return Request()


class Service:
    def __init__(self):
        self.events_api = Events()

    def events(self):
        return self.events_api


def sample_event() -> CalendarEvent:
    return CalendarEvent(
        summary="Confirmed appointment",
        start_at="2026-09-01T10:00:00-07:00",
        end_at="2026-09-01T11:00:00-07:00",
        timezone="America/Los_Angeles",
        attendee_email="person@example.com",
        fingerprint="abc123",
        source_message_id="gmail-1",
        location="Office",
    )


def test_create_event_is_deduplicated_and_minimal():
    service = Service()
    connector = GoogleCalendarConnector(service)

    created = connector.create_event(sample_event())

    assert created["id"] == "event-1"
    operation, call = service.events_api.calls[-1]
    assert operation == "insert"
    assert call["sendUpdates"] == "all"
    assert call["body"]["attendees"] == [{"email": "person@example.com"}]
    assert "description" not in call["body"]
    assert call["body"]["extendedProperties"]["private"] == {
        "life_os_fingerprint": "abc123",
        "life_os_source_message_id": "gmail-1",
    }


def test_existing_fingerprint_prevents_duplicate_insert():
    service = Service()
    service.events_api.list_result = {"items": [{"id": "existing"}]}
    connector = GoogleCalendarConnector(service)

    result = connector.create_event(sample_event())

    assert result["id"] == "existing"
    assert [operation for operation, _ in service.events_api.calls] == ["list"]


def test_delete_event_sends_guest_updates():
    service = Service()
    connector = GoogleCalendarConnector(service)

    connector.delete_event("event-1")

    assert service.events_api.calls == [
        (
            "delete",
            {
                "calendarId": "primary",
                "eventId": "event-1",
                "sendUpdates": "all",
            },
        )
    ]
