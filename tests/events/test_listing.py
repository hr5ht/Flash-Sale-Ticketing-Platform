from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import AsyncClient

from tests.events.conftest import event_payload


async def publish(
    client: AsyncClient, headers: dict[str, str], **overrides: Any
) -> dict[str, Any]:
    created = await client.post(
        "/events", json=event_payload(**overrides), headers=headers
    )
    event_id = created.json()["id"]
    published = await client.post(f"/events/{event_id}/publish", headers=headers)
    return published.json()


async def test_listing_excludes_draft_events(
    draft_event: dict[str, Any], client: AsyncClient
) -> None:
    response = await client.get("/events")

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 0


async def test_listing_includes_published_events(
    published_event: dict[str, Any], client: AsyncClient
) -> None:
    response = await client.get("/events")

    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == published_event["id"]


async def test_listing_reports_minimum_price(
    published_event: dict[str, Any], client: AsyncClient
) -> None:
    response = await client.get("/events")

    assert response.json()["items"][0]["min_price_cents"] == 250000


async def test_listing_filters_by_city_case_insensitively(
    organizer_headers: dict[str, str], client: AsyncClient
) -> None:
    await publish(client, organizer_headers, city="Bengaluru")
    await publish(client, organizer_headers, title="Other", city="Mumbai")

    response = await client.get("/events", params={"city": "bENGALURU"})

    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["city"] == "Bengaluru"


async def test_listing_filters_by_category(
    organizer_headers: dict[str, str], client: AsyncClient
) -> None:
    await publish(client, organizer_headers, category="concert")
    await publish(client, organizer_headers, title="Final", category="sports")

    response = await client.get("/events", params={"category": "sports"})

    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["category"] == "sports"


async def test_listing_filters_by_date_range(
    organizer_headers: dict[str, str], client: AsyncClient
) -> None:
    soon = datetime.now(UTC) + timedelta(days=10)
    later = datetime.now(UTC) + timedelta(days=90)
    await publish(
        client,
        organizer_headers,
        title="Soon",
        starts_at=soon.isoformat(),
        sale_starts_at=(soon - timedelta(days=5)).isoformat(),
    )
    await publish(
        client,
        organizer_headers,
        title="Later",
        starts_at=later.isoformat(),
        sale_starts_at=(later - timedelta(days=5)).isoformat(),
    )

    response = await client.get(
        "/events",
        params={"starts_after": (datetime.now(UTC) + timedelta(days=30)).isoformat()},
    )

    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Later"


async def test_listing_is_ordered_by_start_time(
    organizer_headers: dict[str, str], client: AsyncClient
) -> None:
    later = datetime.now(UTC) + timedelta(days=90)
    soon = datetime.now(UTC) + timedelta(days=10)
    await publish(
        client,
        organizer_headers,
        title="Later",
        starts_at=later.isoformat(),
        sale_starts_at=(later - timedelta(days=5)).isoformat(),
    )
    await publish(
        client,
        organizer_headers,
        title="Soon",
        starts_at=soon.isoformat(),
        sale_starts_at=(soon - timedelta(days=5)).isoformat(),
    )

    response = await client.get("/events")

    assert [item["title"] for item in response.json()["items"]] == ["Soon", "Later"]


async def test_listing_paginates(
    organizer_headers: dict[str, str], client: AsyncClient
) -> None:
    for index in range(3):
        starts_at = datetime.now(UTC) + timedelta(days=10 + index)
        await publish(
            client,
            organizer_headers,
            title=f"Event {index}",
            starts_at=starts_at.isoformat(),
            sale_starts_at=(starts_at - timedelta(days=5)).isoformat(),
        )

    response = await client.get("/events", params={"limit": 2, "offset": 0})
    second = await client.get("/events", params={"limit": 2, "offset": 2})

    assert response.json()["total"] == 3
    assert [item["title"] for item in response.json()["items"]] == ["Event 0", "Event 1"]
    assert [item["title"] for item in second.json()["items"]] == ["Event 2"]


async def test_listing_rejects_limit_above_maximum(client: AsyncClient) -> None:
    response = await client.get("/events", params={"limit": 500})

    assert response.status_code == 422


async def test_mine_returns_own_drafts_only(
    draft_event: dict[str, Any],
    organizer_headers: dict[str, str],
    client: AsyncClient,
) -> None:
    response = await client.get("/events/mine", headers=organizer_headers)

    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == draft_event["id"]
    assert body["items"][0]["status"] == "draft"


async def test_mine_requires_organizer_role(
    attendee_headers: dict[str, str], client: AsyncClient
) -> None:
    response = await client.get("/events/mine", headers=attendee_headers)

    assert response.status_code == 403
