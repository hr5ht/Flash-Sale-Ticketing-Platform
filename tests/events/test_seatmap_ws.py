import json
from typing import Any

from httpx import AsyncClient

from src.seatmap.connections import connections
from tests.sockets import next_message, open_socket


async def test_sends_seat_map_on_connect(published_event: dict[str, Any]) -> None:
    async with open_socket(f"/events/{published_event['id']}/seatmap/ws") as messages:
        message = await next_message(messages)

    seat_map = json.loads(message["text"])
    assert seat_map["event_id"] == published_event["id"]
    assert [section["name"] for section in seat_map["sections"]] == [
        "Orchestra",
        "Balcony",
    ]


async def test_connection_is_tracked_until_disconnect(
    published_event: dict[str, Any],
) -> None:
    event_id = published_event["id"]
    async with open_socket(f"/events/{event_id}/seatmap/ws") as messages:
        await next_message(messages)
        assert len(connections[event_id]) == 1

    assert event_id not in connections


async def test_draft_is_hidden_from_anonymous(draft_event: dict[str, Any]) -> None:
    async with open_socket(f"/events/{draft_event['id']}/seatmap/ws") as messages:
        message = await next_message(messages)

    assert message == {"type": "websocket.close", "code": 4404, "reason": ""}


async def test_organizer_sees_own_draft(
    draft_event: dict[str, Any], organizer_headers: dict[str, str]
) -> None:
    token = organizer_headers["Authorization"].removeprefix("Bearer ")
    url = f"/events/{draft_event['id']}/seatmap/ws?token={token}"
    async with open_socket(url) as messages:
        message = await next_message(messages)

    assert json.loads(message["text"])["event_id"] == draft_event["id"]


async def test_bad_token_is_rejected(published_event: dict[str, Any]) -> None:
    url = f"/events/{published_event['id']}/seatmap/ws?token=nope"
    async with open_socket(url) as messages:
        message = await next_message(messages)

    assert message["code"] == 4401


async def test_unknown_event(client: AsyncClient) -> None:
    async with open_socket("/events/987654/seatmap/ws") as messages:
        message = await next_message(messages)

    assert message["code"] == 4404
