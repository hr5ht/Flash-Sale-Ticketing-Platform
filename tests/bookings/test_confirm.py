from typing import Any

from httpx import AsyncClient
from sqlalchemy import text


async def hold(
    client: AsyncClient, event_id: int, seat_ids: list[int], headers: dict[str, str]
) -> dict[str, Any]:
    response = await client.post(
        f"/events/{event_id}/holds", json={"seat_ids": seat_ids}, headers=headers
    )
    return response.json()


async def test_confirm_turns_a_hold_into_a_booking(
    event_seats: list[int],
    on_sale_event: dict[str, Any],
    buyer_headers: dict[str, str],
    client: AsyncClient,
) -> None:
    seat_map = (await client.get(f"/events/{on_sale_event['id']}/seatmap")).json()
    prices = {tier["id"]: tier["price_cents"] for tier in seat_map["price_tiers"]}
    tier_of = {
        seat["id"]: seat["price_tier_id"]
        for section in seat_map["sections"]
        for row in section["rows"]
        for seat in row["seats"]
    }
    chosen = event_seats[:2]
    expected = sum(prices[tier_of[seat_id]] for seat_id in chosen)

    held = await hold(client, on_sale_event["id"], chosen, buyer_headers)
    response = await client.post(
        f"/holds/{held['id']}/confirm", headers=buyer_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["hold_id"] == held["id"]
    assert body["seat_ids"] == held["seat_ids"]
    assert body["total_cents"] == expected


async def test_booked_seats_show_as_booked_and_stay_claimed(
    event_seats: list[int],
    on_sale_event: dict[str, Any],
    buyer_headers: dict[str, str],
    rival_headers: dict[str, str],
    client: AsyncClient,
) -> None:
    held = await hold(client, on_sale_event["id"], event_seats[:1], buyer_headers)
    await client.post(f"/holds/{held['id']}/confirm", headers=buyer_headers)

    seat_map = await client.get(f"/events/{on_sale_event['id']}/seatmap")
    statuses = {
        seat["id"]: seat["status"]
        for section in seat_map.json()["sections"]
        for row in section["rows"]
        for seat in row["seats"]
    }
    assert statuses[event_seats[0]] == "booked"

    response = await client.post(
        f"/events/{on_sale_event['id']}/holds",
        json={"seat_ids": event_seats[:1]},
        headers=rival_headers,
    )
    assert response.status_code == 409


async def test_a_booked_seat_is_never_freed_by_expiry(
    event_seats: list[int],
    on_sale_event: dict[str, Any],
    buyer_headers: dict[str, str],
    rival_headers: dict[str, str],
    client: AsyncClient,
    session,
) -> None:
    held = await hold(client, on_sale_event["id"], event_seats[:1], buyer_headers)
    await client.post(f"/holds/{held['id']}/confirm", headers=buyer_headers)

    await session.execute(
        text("UPDATE holds SET expires_at = now() - interval '1 day' WHERE id = :id"),
        {"id": held["id"]},
    )

    response = await client.post(
        f"/events/{on_sale_event['id']}/holds",
        json={"seat_ids": event_seats[:1]},
        headers=rival_headers,
    )

    assert response.status_code == 409


async def test_only_the_holder_can_confirm(
    event_seats: list[int],
    on_sale_event: dict[str, Any],
    buyer_headers: dict[str, str],
    rival_headers: dict[str, str],
    client: AsyncClient,
) -> None:
    held = await hold(client, on_sale_event["id"], event_seats[:1], buyer_headers)

    response = await client.post(
        f"/holds/{held['id']}/confirm", headers=rival_headers
    )

    assert response.status_code == 404


async def test_an_expired_hold_cannot_be_confirmed(
    event_seats: list[int],
    on_sale_event: dict[str, Any],
    buyer_headers: dict[str, str],
    client: AsyncClient,
    session,
) -> None:
    held = await hold(client, on_sale_event["id"], event_seats[:1], buyer_headers)
    await session.execute(
        text("UPDATE holds SET expires_at = now() - interval '1 second' WHERE id = :id"),
        {"id": held["id"]},
    )

    response = await client.post(
        f"/holds/{held['id']}/confirm", headers=buyer_headers
    )

    assert response.status_code == 409


async def test_a_released_hold_cannot_be_confirmed(
    event_seats: list[int],
    on_sale_event: dict[str, Any],
    buyer_headers: dict[str, str],
    client: AsyncClient,
) -> None:
    held = await hold(client, on_sale_event["id"], event_seats[:1], buyer_headers)
    await client.delete(f"/holds/{held['id']}", headers=buyer_headers)

    response = await client.post(
        f"/holds/{held['id']}/confirm", headers=buyer_headers
    )

    assert response.status_code == 409


async def test_confirming_twice_without_a_key_is_refused(
    event_seats: list[int],
    on_sale_event: dict[str, Any],
    buyer_headers: dict[str, str],
    client: AsyncClient,
) -> None:
    held = await hold(client, on_sale_event["id"], event_seats[:1], buyer_headers)
    await client.post(f"/holds/{held['id']}/confirm", headers=buyer_headers)

    response = await client.post(
        f"/holds/{held['id']}/confirm", headers=buyer_headers
    )

    assert response.status_code == 409


async def test_a_confirmed_hold_cannot_be_released(
    event_seats: list[int],
    on_sale_event: dict[str, Any],
    buyer_headers: dict[str, str],
    client: AsyncClient,
) -> None:
    held = await hold(client, on_sale_event["id"], event_seats[:1], buyer_headers)
    await client.post(f"/holds/{held['id']}/confirm", headers=buyer_headers)

    response = await client.delete(f"/holds/{held['id']}", headers=buyer_headers)

    assert response.status_code == 409
