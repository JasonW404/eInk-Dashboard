from __future__ import annotations

from inkpi.admin.events import AdminEventLog


def test_admin_event_log_redacts_sensitive_details() -> None:
    log = AdminEventLog()

    event = log.record(
        source="network",
        message="queued",
        details={
            "ssid": "LabNet",
            "password": "secret",
            "nested": {"api_token": "abc123"},
        },
    )

    assert event.details["ssid"] == "LabNet"
    assert event.details["password"] == "[redacted]"
    assert event.details["nested"] == {"api_token": "[redacted]"}


def test_admin_event_log_is_bounded() -> None:
    log = AdminEventLog(capacity=2)

    log.record(source="test", message="one")
    log.record(source="test", message="two")
    log.record(source="test", message="three")

    assert [event.message for event in log.list_events()] == ["two", "three"]
