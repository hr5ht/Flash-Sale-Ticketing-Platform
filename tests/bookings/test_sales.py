from typing import Any

from httpx import AsyncClient
from sqlalchemy import text


async def test_bookings_list_is_scoped_to_the_user(
    event_seats: list[int],
    on_sale_event: dict[str, Any],
    buyer_headers: dict[str, str],
    rival_headers: dict[str, str],
    client: AsyncClient,
) -> None:
    held = await client.post(
        f"/events/{on_sale_event['id']}/holds",
        json={"seat_ids": event_seats[:1]},
        headers=buyer_headers,
    )
    await client.post(f"/holds/{held.json()['id']}/confirm", headers=buyer_headers)

    mine = await client.get("/bookings", headers=buyer_headers)
    theirs = await client.get("/bookings", headers=rival_headers)

    assert mine.json()["total"] == 1
    assert theirs.json()["total"] == 0


async def test_booking_detail_is_hidden_from_other_users(
    event_seats: list[int],
    on_sale_event: dict[str, Any],
    buyer_headers: dict[str, str],
    rival_headers: dict[str, str],
    client: AsyncClient,
) -> None:
    held = await client.post(
        f"/events/{on_sale_event['id']}/holds",
        json={"seat_ids": event_seats[:1]},
        headers=buyer_headers,
    )
    booking = await client.post(
        f"/holds/{held.json()['id']}/confirm", headers=buyer_headers
    )

    response = await client.get(
        f"/bookings/{booking.json()['id']}", headers=rival_headers
    )

    assert response.status_code == 404


async def test_sales_summary_counts_seats_and_revenue(
    event_seats: list[int],
    on_sale_event: dict[str, Any],
    organizer_headers: dict[str, str],
    buyer_headers: dict[str, str],
    rival_headers: dict[str, str],
    client: AsyncClient,
) -> None:
    booked = await client.post(
        f"/events/{on_sale_event['id']}/holds",
        json={"seat_ids": event_seats[:2]},
        headers=buyer_headers,
    )
    confirmed = await client.post(
        f"/holds/{booked.json()['id']}/confirm", headers=buyer_headers
    )
    await client.post(
        f"/events/{on_sale_event['id']}/holds",
        json={"seat_ids": event_seats[2:5]},
        headers=rival_headers,
    )

    response = await client.get(
        f"/events/{on_sale_event['id']}/sales", headers=organizer_headers
    )

    body = response.json()
    assert body["seats_total"] == 9
    assert body["seats_booked"] == 2
    assert body["seats_held"] == 3
    assert body["seats_available"] == 4
    assert body["bookings"] == 1
    assert body["gross_cents"] == confirmed.json()["total_cents"]


async def test_sales_summary_ignores_expired_holds(
    event_seats: list[int],
    on_sale_event: dict[str, Any],
    organizer_headers: dict[str, str],
    buyer_headers: dict[str, str],
    client: AsyncClient,
    session,
) -> None:
    held = await client.post(
        f"/events/{on_sale_event['id']}/holds",
        json={"seat_ids": event_seats[:3]},
        headers=buyer_headers,
    )
    await session.execute(
        text("UPDATE holds SET expires_at = now() - interval '1 second' WHERE id = :id"),
        {"id": held.json()["id"]},
    )

    response = await client.get(
        f"/events/{on_sale_event['id']}/sales", headers=organizer_headers
    )

    body = response.json()
    assert body["seats_held"] == 0
    assert body["seats_available"] == 9


async def test_sales_summary_is_refused_to_other_organizers(
    on_sale_event: dict[str, Any], buyer_headers: dict[str, str], client: AsyncClient
) -> None:
    response = await client.get(
        f"/events/{on_sale_event['id']}/sales", headers=buyer_headers
    )

    assert response.status_code == 403
