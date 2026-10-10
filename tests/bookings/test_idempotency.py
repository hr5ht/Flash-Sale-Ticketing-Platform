from typing import Any

from httpx import AsyncClient


async def test_repeating_a_hold_with_the_same_key_returns_the_original(
    event_seats: list[int],
    on_sale_event: dict[str, Any],
    buyer_headers: dict[str, str],
    client: AsyncClient,
) -> None:
    headers = {**buyer_headers, "Idempotency-Key": "hold-1"}
    first = await client.post(
        f"/events/{on_sale_event['id']}/holds",
        json={"seat_ids": event_seats[:2]},
        headers=headers,
    )

    second = await client.post(
        f"/events/{on_sale_event['id']}/holds",
        json={"seat_ids": event_seats[:2]},
        headers=headers,
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["seat_ids"] == second.json()["seat_ids"]


async def test_retried_hold_does_not_consume_the_seat_limit_twice(
    event_seats: list[int],
    on_sale_event: dict[str, Any],
    buyer_headers: dict[str, str],
    client: AsyncClient,
) -> None:
    headers = {**buyer_headers, "Idempotency-Key": "hold-1"}
    for _ in range(4):
        await client.post(
            f"/events/{on_sale_event['id']}/holds",
            json={"seat_ids": event_seats[:4]},
            headers=headers,
        )

    response = await client.post(
        f"/events/{on_sale_event['id']}/holds",
        json={"seat_ids": event_seats[4:6]},
        headers=buyer_headers,
    )

    assert response.status_code == 201


async def test_a_different_key_creates_a_new_hold(
    event_seats: list[int],
    on_sale_event: dict[str, Any],
    buyer_headers: dict[str, str],
    client: AsyncClient,
) -> None:
    first = await client.post(
        f"/events/{on_sale_event['id']}/holds",
        json={"seat_ids": event_seats[:1]},
        headers={**buyer_headers, "Idempotency-Key": "hold-1"},
    )
    second = await client.post(
        f"/events/{on_sale_event['id']}/holds",
        json={"seat_ids": event_seats[1:2]},
        headers={**buyer_headers, "Idempotency-Key": "hold-2"},
    )

    assert first.json()["id"] != second.json()["id"]


async def test_two_users_may_reuse_the_same_key(
    event_seats: list[int],
    on_sale_event: dict[str, Any],
    buyer_headers: dict[str, str],
    rival_headers: dict[str, str],
    client: AsyncClient,
) -> None:
    first = await client.post(
        f"/events/{on_sale_event['id']}/holds",
        json={"seat_ids": event_seats[:1]},
        headers={**buyer_headers, "Idempotency-Key": "shared"},
    )
    second = await client.post(
        f"/events/{on_sale_event['id']}/holds",
        json={"seat_ids": event_seats[1:2]},
        headers={**rival_headers, "Idempotency-Key": "shared"},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]


async def test_repeating_a_confirm_with_the_same_key_returns_the_original(
    event_seats: list[int],
    on_sale_event: dict[str, Any],
    buyer_headers: dict[str, str],
    client: AsyncClient,
) -> None:
    held = await client.post(
        f"/events/{on_sale_event['id']}/holds",
        json={"seat_ids": event_seats[:1]},
        headers=buyer_headers,
    )
    headers = {**buyer_headers, "Idempotency-Key": "confirm-1"}

    first = await client.post(
        f"/holds/{held.json()['id']}/confirm", headers=headers
    )
    second = await client.post(
        f"/holds/{held.json()['id']}/confirm", headers=headers
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["total_cents"] == second.json()["total_cents"]


async def test_retried_confirm_creates_only_one_booking(
    event_seats: list[int],
    on_sale_event: dict[str, Any],
    buyer_headers: dict[str, str],
    client: AsyncClient,
) -> None:
    held = await client.post(
        f"/events/{on_sale_event['id']}/holds",
        json={"seat_ids": event_seats[:1]},
        headers=buyer_headers,
    )
    headers = {**buyer_headers, "Idempotency-Key": "confirm-1"}
    for _ in range(3):
        await client.post(f"/holds/{held.json()['id']}/confirm", headers=headers)

    bookings = await client.get("/bookings", headers=buyer_headers)

    assert bookings.json()["total"] == 1
