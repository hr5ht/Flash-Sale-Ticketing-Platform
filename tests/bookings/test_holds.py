from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import AsyncClient
from sqlalchemy import text

from tests.bookings.conftest import create_on_sale_event, seat_ids_of
from tests.events.conftest import event_payload


async def test_hold_claims_every_requested_seat(
    event_seats: list[int],
    on_sale_event: dict[str, Any],
    buyer_headers: dict[str, str],
    client: AsyncClient,
) -> None:
    response = await client.post(
        f"/events/{on_sale_event['id']}/holds",
        json={"seat_ids": event_seats[:3]},
        headers=buyer_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["seat_ids"] == sorted(event_seats[:3])
    assert body["state"] == "active"


async def test_hold_is_all_or_nothing(
    event_seats: list[int],
    on_sale_event: dict[str, Any],
    buyer_headers: dict[str, str],
    rival_headers: dict[str, str],
    client: AsyncClient,
) -> None:
    await client.post(
        f"/events/{on_sale_event['id']}/holds",
        json={"seat_ids": [event_seats[0]]},
        headers=rival_headers,
    )

    response = await client.post(
        f"/events/{on_sale_event['id']}/holds",
        json={"seat_ids": [event_seats[0], event_seats[1], event_seats[2]]},
        headers=buyer_headers,
    )

    assert response.status_code == 409

    seat_map = await client.get(f"/events/{on_sale_event['id']}/seatmap")
    statuses = {
        seat["id"]: seat["status"]
        for section in seat_map.json()["sections"]
        for row in section["rows"]
        for seat in row["seats"]
    }
    assert statuses[event_seats[1]] == "available"
    assert statuses[event_seats[2]] == "available"


async def test_held_seats_show_as_held_on_the_seat_map(
    event_seats: list[int],
    on_sale_event: dict[str, Any],
    buyer_headers: dict[str, str],
    client: AsyncClient,
) -> None:
    await client.post(
        f"/events/{on_sale_event['id']}/holds",
        json={"seat_ids": [event_seats[0]]},
        headers=buyer_headers,
    )

    seat_map = await client.get(f"/events/{on_sale_event['id']}/seatmap")
    statuses = {
        seat["id"]: seat["status"]
        for section in seat_map.json()["sections"]
        for row in section["rows"]
        for seat in row["seats"]
    }

    assert statuses[event_seats[0]] == "held"


async def test_expired_hold_frees_its_seats_without_any_background_process(
    event_seats: list[int],
    on_sale_event: dict[str, Any],
    buyer_headers: dict[str, str],
    rival_headers: dict[str, str],
    client: AsyncClient,
    session,
) -> None:
    held = await client.post(
        f"/events/{on_sale_event['id']}/holds",
        json={"seat_ids": [event_seats[0]]},
        headers=buyer_headers,
    )
    hold_id = held.json()["id"]

    await session.execute(
        text("UPDATE holds SET expires_at = now() - interval '1 second' WHERE id = :id"),
        {"id": hold_id},
    )

    seat_map = await client.get(f"/events/{on_sale_event['id']}/seatmap")
    statuses = {
        seat["id"]: seat["status"]
        for section in seat_map.json()["sections"]
        for row in section["rows"]
        for seat in row["seats"]
    }
    assert statuses[event_seats[0]] == "available"

    response = await client.post(
        f"/events/{on_sale_event['id']}/holds",
        json={"seat_ids": [event_seats[0]]},
        headers=rival_headers,
    )
    assert response.status_code == 201


async def test_releasing_a_hold_frees_its_seats(
    event_seats: list[int],
    on_sale_event: dict[str, Any],
    buyer_headers: dict[str, str],
    rival_headers: dict[str, str],
    client: AsyncClient,
) -> None:
    held = await client.post(
        f"/events/{on_sale_event['id']}/holds",
        json={"seat_ids": [event_seats[0]]},
        headers=buyer_headers,
    )

    released = await client.delete(
        f"/holds/{held.json()['id']}", headers=buyer_headers
    )
    assert released.status_code == 204

    response = await client.post(
        f"/events/{on_sale_event['id']}/holds",
        json={"seat_ids": [event_seats[0]]},
        headers=rival_headers,
    )
    assert response.status_code == 201


async def test_only_the_holder_can_release(
    event_seats: list[int],
    on_sale_event: dict[str, Any],
    buyer_headers: dict[str, str],
    rival_headers: dict[str, str],
    client: AsyncClient,
) -> None:
    held = await client.post(
        f"/events/{on_sale_event['id']}/holds",
        json={"seat_ids": [event_seats[0]]},
        headers=buyer_headers,
    )

    response = await client.delete(
        f"/holds/{held.json()['id']}", headers=rival_headers
    )

    assert response.status_code == 404


async def test_seat_limit_per_event_is_enforced(
    on_sale_event: dict[str, Any],
    buyer_headers: dict[str, str],
    client: AsyncClient,
) -> None:
    seats = await seat_ids_of(client, on_sale_event["id"])

    response = await client.post(
        f"/events/{on_sale_event['id']}/holds",
        json={"seat_ids": seats[:7]},
        headers=buyer_headers,
    )

    assert response.status_code == 409


async def test_seat_limit_counts_seats_across_holds(
    event_seats: list[int],
    on_sale_event: dict[str, Any],
    buyer_headers: dict[str, str],
    client: AsyncClient,
) -> None:
    await client.post(
        f"/events/{on_sale_event['id']}/holds",
        json={"seat_ids": event_seats[:4]},
        headers=buyer_headers,
    )

    response = await client.post(
        f"/events/{on_sale_event['id']}/holds",
        json={"seat_ids": event_seats[4:7]},
        headers=buyer_headers,
    )

    assert response.status_code == 409


async def test_seats_from_another_event_are_rejected(
    on_sale_event: dict[str, Any],
    organizer_headers: dict[str, str],
    buyer_headers: dict[str, str],
    client: AsyncClient,
) -> None:
    other = await create_on_sale_event(client, organizer_headers, title="Other")
    other_seats = await seat_ids_of(client, other["id"])

    response = await client.post(
        f"/events/{on_sale_event['id']}/holds",
        json={"seat_ids": other_seats[:1]},
        headers=buyer_headers,
    )

    assert response.status_code == 422


async def test_holds_are_refused_before_the_sale_starts(
    organizer_headers: dict[str, str], buyer_headers: dict[str, str], client: AsyncClient
) -> None:
    starts_at = datetime.now(UTC) + timedelta(days=30)
    payload = event_payload(
        starts_at=starts_at.isoformat(),
        sale_starts_at=(datetime.now(UTC) + timedelta(days=1)).isoformat(),
    )
    created = await client.post("/events", json=payload, headers=organizer_headers)
    event_id = created.json()["id"]
    await client.post(f"/events/{event_id}/publish", headers=organizer_headers)
    seats = await seat_ids_of(client, event_id)

    response = await client.post(
        f"/events/{event_id}/holds",
        json={"seat_ids": seats[:1]},
        headers=buyer_headers,
    )

    assert response.status_code == 409


async def test_holds_are_refused_on_a_draft_event(
    organizer_headers: dict[str, str],
    buyer_headers: dict[str, str],
    client: AsyncClient,
) -> None:
    created = await client.post(
        "/events", json=event_payload(), headers=organizer_headers
    )
    draft_id = created.json()["id"]

    response = await client.post(
        f"/events/{draft_id}/holds",
        json={"seat_ids": [1]},
        headers=buyer_headers,
    )

    assert response.status_code == 404


async def test_anonymous_users_cannot_hold(
    event_seats: list[int], on_sale_event: dict[str, Any], client: AsyncClient
) -> None:
    response = await client.post(
        f"/events/{on_sale_event['id']}/holds", json={"seat_ids": event_seats[:1]}
    )

    assert response.status_code == 401
