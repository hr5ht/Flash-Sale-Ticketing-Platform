from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import AsyncClient

from tests.events.conftest import event_payload


async def test_organizer_creates_draft_event(
    organizer_headers: dict[str, str], client: AsyncClient
) -> None:
    response = await client.post(
        "/events", json=event_payload(), headers=organizer_headers
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "draft"
    assert body["title"] == "Midnight Symphony"
    assert [tier["name"] for tier in body["price_tiers"]] == ["Silver", "Gold"]


async def test_created_event_generates_every_seat(
    draft_event: dict[str, Any], organizer_headers: dict[str, str], client: AsyncClient
) -> None:
    response = await client.get(
        f"/events/{draft_event['id']}/seatmap", headers=organizer_headers
    )

    seat_map = response.json()
    seats = [
        seat
        for section in seat_map["sections"]
        for row in section["rows"]
        for seat in row["seats"]
    ]
    assert len(seats) == 9
    assert len({seat["id"] for seat in seats}) == 9


async def test_attendee_cannot_create_event(
    attendee_headers: dict[str, str], client: AsyncClient
) -> None:
    response = await client.post(
        "/events", json=event_payload(), headers=attendee_headers
    )

    assert response.status_code == 403


async def test_anonymous_cannot_create_event(client: AsyncClient) -> None:
    response = await client.post("/events", json=event_payload())

    assert response.status_code == 401


async def test_create_rejects_row_referencing_unknown_tier(
    organizer_headers: dict[str, str], client: AsyncClient
) -> None:
    payload = event_payload(
        sections=[
            {
                "name": "Orchestra",
                "rows": [{"label": "A", "seat_count": 2, "price_tier": "Platinum"}],
            }
        ]
    )

    response = await client.post("/events", json=payload, headers=organizer_headers)

    assert response.status_code == 422


async def test_create_rejects_duplicate_tier_names(
    organizer_headers: dict[str, str], client: AsyncClient
) -> None:
    payload = event_payload(
        price_tiers=[
            {"name": "Gold", "price_cents": 500000},
            {"name": "Gold", "price_cents": 250000},
        ]
    )

    response = await client.post("/events", json=payload, headers=organizer_headers)

    assert response.status_code == 422


async def test_create_rejects_sale_starting_after_event(
    organizer_headers: dict[str, str], client: AsyncClient
) -> None:
    starts_at = datetime.now(UTC) + timedelta(days=10)
    payload = event_payload(
        starts_at=starts_at.isoformat(),
        sale_starts_at=(starts_at + timedelta(days=1)).isoformat(),
    )

    response = await client.post("/events", json=payload, headers=organizer_headers)

    assert response.status_code == 422


async def test_create_rejects_naive_datetime(
    organizer_headers: dict[str, str], client: AsyncClient
) -> None:
    payload = event_payload(starts_at="2027-01-01T20:00:00")

    response = await client.post("/events", json=payload, headers=organizer_headers)

    assert response.status_code == 422


async def test_create_rejects_zero_price_tier(
    organizer_headers: dict[str, str], client: AsyncClient
) -> None:
    payload = event_payload(price_tiers=[{"name": "Free", "price_cents": 0}])

    response = await client.post("/events", json=payload, headers=organizer_headers)

    assert response.status_code == 422


async def test_create_rejects_event_exceeding_seat_cap(
    organizer_headers: dict[str, str], client: AsyncClient
) -> None:
    payload = event_payload(
        sections=[
            {
                "name": "Stadium",
                "rows": [
                    {"label": str(index), "seat_count": 200, "price_tier": "Gold"}
                    for index in range(30)
                ],
            }
        ]
    )

    response = await client.post("/events", json=payload, headers=organizer_headers)

    assert response.status_code == 422
