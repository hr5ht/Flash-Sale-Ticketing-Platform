import asyncio
import json
from typing import Any

from httpx import AsyncClient

from tests.sockets import next_message, open_socket


async def next_update(messages: asyncio.Queue[dict[str, Any]]) -> dict[str, Any]:
    return json.loads((await next_message(messages))["text"])


async def test_hold_then_confirm(
    event_seats: list[int],
    on_sale_event: dict[str, Any],
    buyer_headers: dict[str, str],
    client: AsyncClient,
) -> None:
    event_id = on_sale_event["id"]
    async with open_socket(f"/events/{event_id}/seatmap/ws") as messages:
        await next_message(messages)

        held = await client.post(
            f"/events/{event_id}/holds",
            json={"seat_ids": event_seats[:2]},
            headers=buyer_headers,
        )
        assert await next_update(messages) == {
            "status": "held",
            "seat_ids": event_seats[:2],
        }

        await client.post(f"/holds/{held.json()['id']}/confirm", headers=buyer_headers)
        assert await next_update(messages) == {
            "status": "booked",
            "seat_ids": event_seats[:2],
        }


async def test_release_frees_seats(
    event_seats: list[int],
    on_sale_event: dict[str, Any],
    buyer_headers: dict[str, str],
    client: AsyncClient,
) -> None:
    event_id = on_sale_event["id"]
    async with open_socket(f"/events/{event_id}/seatmap/ws") as messages:
        await next_message(messages)

        held = await client.post(
            f"/events/{event_id}/holds",
            json={"seat_ids": event_seats[:1]},
            headers=buyer_headers,
        )
        await next_update(messages)
        await client.delete(f"/holds/{held.json()['id']}", headers=buyer_headers)

        assert await next_update(messages) == {
            "status": "available",
            "seat_ids": event_seats[:1],
        }


async def test_cancel_frees_seats(
    event_seats: list[int],
    on_sale_event: dict[str, Any],
    buyer_headers: dict[str, str],
    client: AsyncClient,
) -> None:
    event_id = on_sale_event["id"]
    held = await client.post(
        f"/events/{event_id}/holds",
        json={"seat_ids": event_seats[:1]},
        headers=buyer_headers,
    )
    booking = await client.post(
        f"/holds/{held.json()['id']}/confirm", headers=buyer_headers
    )

    async with open_socket(f"/events/{event_id}/seatmap/ws") as messages:
        await next_message(messages)
        await client.delete(f"/bookings/{booking.json()['id']}", headers=buyer_headers)

        assert await next_update(messages) == {
            "status": "available",
            "seat_ids": event_seats[:1],
        }


async def test_failed_hold_sends_nothing(
    event_seats: list[int],
    on_sale_event: dict[str, Any],
    buyer_headers: dict[str, str],
    rival_headers: dict[str, str],
    client: AsyncClient,
) -> None:
    event_id = on_sale_event["id"]
    await client.post(
        f"/events/{event_id}/holds",
        json={"seat_ids": event_seats[:1]},
        headers=buyer_headers,
    )

    async with open_socket(f"/events/{event_id}/seatmap/ws") as messages:
        await next_message(messages)
        rejected = await client.post(
            f"/events/{event_id}/holds",
            json={"seat_ids": event_seats[:2]},
            headers=rival_headers,
        )

        assert rejected.status_code == 409
        assert messages.empty()
