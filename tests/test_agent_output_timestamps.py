from datetime import datetime

from life_os.models import ProposedAction


def test_relative_action_timestamps_are_normalized() -> None:
    immediate = ProposedAction(title="Eat lunch", domain="nutrition", due_at="now")
    today = ProposedAction(title="Take vitamins", domain="nutrition", due_at="today")

    assert immediate.due_at is not None
    assert immediate.due_at.tzinfo is not None
    assert today.due_at is not None
    assert today.due_at.tzinfo is not None
    assert (today.due_at.hour, today.due_at.minute, today.due_at.second) == (23, 59, 59)


def test_iso_action_timestamp_remains_supported() -> None:
    action = ProposedAction(
        title="Eat dinner",
        domain="nutrition",
        due_at="2030-01-02T21:00:00-08:00",
    )

    assert action.due_at == datetime.fromisoformat("2030-01-02T21:00:00-08:00")
