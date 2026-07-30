from __future__ import annotations

from unittest.mock import MagicMock, patch

from inkpi.network.service import PiNetworkService


def test_pi_network_service_polls_executes_and_reports_without_logging_secret() -> None:
    execute = MagicMock(
        return_value={
            "status": "succeeded",
            "message": "hotspot_configure completed",
        }
    )
    service = PiNetworkService("https://inkpi.example", "network-secret", execute=execute)
    get_response = MagicMock()
    get_response.json.return_value = {
        "id": 7,
        "action": "hotspot_configure",
        "payload": {"ssid": "InkPi", "password": "wifi-secret", "security": "wpa2"},
    }
    post_response = MagicMock()
    service._session.get = MagicMock(return_value=get_response)  # type: ignore[attr-defined]
    service._session.post = MagicMock(return_value=post_response)  # type: ignore[attr-defined]

    with (
        patch("inkpi.network.service.hotspot_is_active", return_value=True),
        patch("inkpi.network.service.connected_hotspot_clients", return_value=3),
    ):
        assert service.run_once() is True

    execute.assert_called_once()
    submitted = execute.call_args.args[0]
    assert submitted["payload"]["password"] == "wifi-secret"
    report = service._session.post.call_args.kwargs["json"]  # type: ignore[attr-defined]
    assert report == {
        "status": "succeeded",
        "message": "hotspot_configure completed",
        "hotspot_active": True,
        "connected_clients": 3,
    }


def test_pi_network_service_handles_empty_queue() -> None:
    service = PiNetworkService("https://inkpi.example", "network-secret")
    response = MagicMock()
    response.json.return_value = None
    service._session.get = MagicMock(return_value=response)  # type: ignore[attr-defined]
    service._session.post = MagicMock(return_value=MagicMock())  # type: ignore[attr-defined]
    assert service.run_once() is False
    assert service._session.post.call_args.args[0].endswith("/api/network/status")  # type: ignore[attr-defined]
