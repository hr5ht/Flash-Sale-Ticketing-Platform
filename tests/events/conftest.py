from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient


def event_payload(**overrides: Any) -> dict[str, Any]:
    starts_at = datetime.now(UTC) + timedelta(days=30)
    payload: dict[str, Any] = {
        "title": "Midnight Symphony",
        "description": "One night only",
        "category": "concert",
        "city": "Bengaluru",
        "venue": "Chowdiah Memorial Hall",
        "starts_at": starts_at.isoformat(),
        "sale_starts_at": (starts_at - timedelta(days=14)).isoformat(),
        "price_tiers": [
            {"name": "Gold", "price_cents": 500000},
            {"name": "Silver", "price_cents": 250000},
        ],
        "sections": [
            {
                "name": "Orchestra",
                "rows": [
                    {"label": "A", "seat_count": 3, "price_tier": "Gold"},
                    {"label": "B", "seat_count": 2, "price_tier": "Silver"},
                ],
            },
            {
                "name": "Balcony",
                "rows": [{"label": "A", "seat_count": 4, "price_tier": "Silver"}],
            },
        ],
    }
    payload.update(overrides)
    return payload



@pytest.fixture
async def draft_event(
    organizer_headers: dict[str, str], client: AsyncClient
) -> dict[str, Any]:
    response = await client.post(
        "/events", json=event_payload(), headers=organizer_headers
    )
    return response.json()


@pytest.fixture
async def published_event(
    draft_event: dict[str, Any], organizer_headers: dict[str, str], client: AsyncClient
) -> dict[str, Any]:
    response = await client.post(
        f"/events/{draft_event['id']}/publish", headers=organizer_headers
    )
    return response.json()
