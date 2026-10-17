import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from httpx import AsyncClient

from src.main import app
from src.seatmap.connections import connections


@asynccontextmanager
async def open_socket(url: str) -> AsyncIterator[asyncio.Queue[dict[str, Any]]]:
    path, _, query = url.partition("?")
    scope = {
        "type": "websocket",
        "path": path,
        "query_string": query.encode(),
        "headers": [],
        "subprotocols": [],
    }
    to_app: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    from_app: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    await to_app.put({"type": "websocket.connect"})
    task = asyncio.create_task(app(scope, to_app.get, from_app.put))
    try:
        accepted = await next_message(from_app)
        assert accepted["type"] == "websocket.accept"
        yield from_app
    finally:
        await to_app.put({"type": "websocket.disconnect", "code": 1000})
        await asyncio.wait_for(task, timeout=5)


async def next_message(messages: asyncio.Queue[dict[str, Any]]) -> dict[str, Any]:
    return await asyncio.wait_for(messages.get(), timeout=5)


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
