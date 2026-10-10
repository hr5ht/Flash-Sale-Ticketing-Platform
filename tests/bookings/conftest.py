from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from tests.events.conftest import event_payload


async def create_user(
    client: AsyncClient, email: str, role: str = "attendee"
) -> dict[str, str]:
    await client.post(
        "/auth/register",
        json={"email": email, "password": "correct horse", "role": role},
    )
    login = await client.post(
        "/auth/login", json={"email": email, "password": "correct horse"}
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def create_on_sale_event(
    client: AsyncClient, headers: dict[str, str], **overrides: Any
) -> dict[str, Any]:
    starts_at = datetime.now(UTC) + timedelta(days=30)
    payload = event_payload(
        starts_at=starts_at.isoformat(),
        sale_starts_at=(datetime.now(UTC) - timedelta(hours=1)).isoformat(),
        **overrides,
    )
    created = await client.post("/events", json=payload, headers=headers)
    event = created.json()
    await client.post(f"/events/{event['id']}/publish", headers=headers)
    return event


async def seat_ids_of(
    client: AsyncClient, event_id: int, headers: dict[str, str] | None = None
) -> list[int]:
    response = await client.get(f"/events/{event_id}/seatmap", headers=headers or {})
    body = response.json()
    return [
        seat["id"]
        for section in body["sections"]
        for row in section["rows"]
        for seat in row["seats"]
    ]


@pytest.fixture
async def buyer_headers(client: AsyncClient) -> dict[str, str]:
    return await create_user(client, "buyer@example.com")


@pytest.fixture
async def rival_headers(client: AsyncClient) -> dict[str, str]:
    return await create_user(client, "rival@example.com")


@pytest.fixture
async def on_sale_event(
    organizer_headers: dict[str, str], client: AsyncClient
) -> dict[str, Any]:
    return await create_on_sale_event(client, organizer_headers)


@pytest.fixture
async def event_seats(on_sale_event: dict[str, Any], client: AsyncClient) -> list[int]:
    return await seat_ids_of(client, on_sale_event["id"])


async def register_buyers(client: AsyncClient, count: int) -> list[dict[str, str]]:
    headers = []
    for index in range(count):
        email = f"buyer{index}@example.com"
        await client.post(
            "/auth/register", json={"email": email, "password": "correct horse"}
        )
        login = await client.post(
            "/auth/login", json={"email": email, "password": "correct horse"}
        )
        headers.append({"Authorization": f"Bearer {login.json()['access_token']}"})
    return headers


async def open_event(client: AsyncClient, seat_count: int) -> tuple[int, list[int]]:
    await client.post(
        "/auth/register",
        json={
            "email": "organizer@example.com",
            "password": "correct horse",
            "role": "organizer",
        },
    )
    login = await client.post(
        "/auth/login",
        json={"email": "organizer@example.com", "password": "correct horse"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    starts_at = datetime.now(UTC) + timedelta(days=30)
    payload = event_payload(
        starts_at=starts_at.isoformat(),
        sale_starts_at=(datetime.now(UTC) - timedelta(hours=1)).isoformat(),
        price_tiers=[{"name": "Gold", "price_cents": 100000}],
        sections=[
            {
                "name": "Floor",
                "rows": [
                    {"label": "A", "seat_count": seat_count, "price_tier": "Gold"}
                ],
            }
        ],
    )
    created = await client.post("/events", json=payload, headers=headers)
    event_id = created.json()["id"]
    await client.post(f"/events/{event_id}/publish", headers=headers)

    seat_map = await client.get(f"/events/{event_id}/seatmap")
    seat_ids = [
        seat["id"]
        for section in seat_map.json()["sections"]
        for row in section["rows"]
        for seat in row["seats"]
    ]
    return event_id, seat_ids


async def count_rows(engine: AsyncEngine, model: Any) -> int:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        return await session.scalar(select(func.count()).select_from(model)) or 0
