from typing import Any

from httpx import AsyncClient


async def book(
    client: AsyncClient, event_id: int, seat_ids: list[int], headers: dict[str, str]
) -> dict[str, Any]:
    held = await client.post(
        f"/events/{event_id}/holds", json={"seat_ids": seat_ids}, headers=headers
    )
    confirmed = await client.post(
        f"/holds/{held.json()['id']}/confirm", headers=headers
    )
    return confirmed.json()


async def test_cancel_frees_the_seats_for_someone_else(
    event_seats: list[int],
    on_sale_event: dict[str, Any],
    organizer_headers: dict[str, str],
    buyer_headers: dict[str, str],
    rival_headers: dict[str, str],
    client: AsyncClient,
) -> None:
    event_id = on_sale_event["id"]
    booking = await book(client, event_id, event_seats[:2], buyer_headers)

    cancelled = await client.delete(f"/bookings/{booking['id']}", headers=buyer_headers)
    mine = await client.get("/bookings", headers=buyer_headers)
    sales = await client.get(f"/events/{event_id}/sales", headers=organizer_headers)
    rival = await client.post(
        f"/events/{event_id}/holds",
        json={"seat_ids": event_seats[:2]},
        headers=rival_headers,
    )

    assert cancelled.status_code == 204
    assert mine.json()["total"] == 0
    assert sales.json()["seats_booked"] == 0
    assert sales.json()["gross_cents"] == 0
    assert rival.status_code == 201


async def test_cancel_twice_is_not_found(
    event_seats: list[int],
    on_sale_event: dict[str, Any],
    buyer_headers: dict[str, str],
    client: AsyncClient,
) -> None:
    booking = await book(client, on_sale_event["id"], event_seats[:1], buyer_headers)

    await client.delete(f"/bookings/{booking['id']}", headers=buyer_headers)
    again = await client.delete(f"/bookings/{booking['id']}", headers=buyer_headers)

    assert again.status_code == 404


async def test_only_the_owner_can_cancel(
    event_seats: list[int],
    on_sale_event: dict[str, Any],
    buyer_headers: dict[str, str],
    rival_headers: dict[str, str],
    client: AsyncClient,
) -> None:
    booking = await book(client, on_sale_event["id"], event_seats[:1], buyer_headers)

    response = await client.delete(f"/bookings/{booking['id']}", headers=rival_headers)
    still_mine = await client.get(f"/bookings/{booking['id']}", headers=buyer_headers)

    assert response.status_code == 404
    assert still_mine.status_code == 200
