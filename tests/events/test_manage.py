from typing import Any

from httpx import AsyncClient

from src.auth.models import Role
from src.auth.service import register_user


async def admin_headers(session, client: AsyncClient) -> dict[str, str]:
    await register_user(session, "admin@example.com", "correct horse", Role.admin)
    response = await client.post(
        "/auth/login",
        json={"email": "admin@example.com", "password": "correct horse"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_publish_moves_event_to_published(
    draft_event: dict[str, Any], organizer_headers: dict[str, str], client: AsyncClient
) -> None:
    response = await client.post(
        f"/events/{draft_event['id']}/publish", headers=organizer_headers
    )

    assert response.status_code == 200
    assert response.json()["status"] == "published"


async def test_publishing_twice_is_rejected(
    published_event: dict[str, Any],
    organizer_headers: dict[str, str],
    client: AsyncClient,
) -> None:
    response = await client.post(
        f"/events/{published_event['id']}/publish", headers=organizer_headers
    )

    assert response.status_code == 409


async def test_other_organizer_cannot_publish(
    draft_event: dict[str, Any], client: AsyncClient
) -> None:
    await client.post(
        "/auth/register",
        json={
            "email": "rival@example.com",
            "password": "correct horse",
            "role": "organizer",
        },
    )
    login = await client.post(
        "/auth/login",
        json={"email": "rival@example.com", "password": "correct horse"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = await client.post(
        f"/events/{draft_event['id']}/publish", headers=headers
    )

    assert response.status_code == 403


async def test_admin_can_publish_another_organizers_event(
    draft_event: dict[str, Any], session, client: AsyncClient
) -> None:
    headers = await admin_headers(session, client)

    response = await client.post(
        f"/events/{draft_event['id']}/publish", headers=headers
    )

    assert response.status_code == 200


async def test_draft_is_invisible_to_anonymous_users(
    draft_event: dict[str, Any], client: AsyncClient
) -> None:
    response = await client.get(f"/events/{draft_event['id']}")

    assert response.status_code == 404


async def test_draft_is_visible_to_its_organizer(
    draft_event: dict[str, Any], organizer_headers: dict[str, str], client: AsyncClient
) -> None:
    response = await client.get(
        f"/events/{draft_event['id']}", headers=organizer_headers
    )

    assert response.status_code == 200
    assert response.json()["id"] == draft_event["id"]


async def test_published_event_is_visible_to_anonymous_users(
    published_event: dict[str, Any], client: AsyncClient
) -> None:
    response = await client.get(f"/events/{published_event['id']}")

    assert response.status_code == 200


async def test_missing_event_returns_404(client: AsyncClient) -> None:
    response = await client.get("/events/123456")

    assert response.status_code == 404


async def test_draft_metadata_can_be_updated(
    draft_event: dict[str, Any], organizer_headers: dict[str, str], client: AsyncClient
) -> None:
    response = await client.patch(
        f"/events/{draft_event['id']}",
        json={"title": "Renamed", "city": "Chennai"},
        headers=organizer_headers,
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Renamed"
    assert response.json()["city"] == "Chennai"
    assert response.json()["venue"] == draft_event["venue"]


async def test_published_event_cannot_be_updated(
    published_event: dict[str, Any],
    organizer_headers: dict[str, str],
    client: AsyncClient,
) -> None:
    response = await client.patch(
        f"/events/{published_event['id']}",
        json={"title": "Renamed"},
        headers=organizer_headers,
    )

    assert response.status_code == 409


async def test_update_rejects_sale_starting_after_event(
    draft_event: dict[str, Any], organizer_headers: dict[str, str], client: AsyncClient
) -> None:
    response = await client.patch(
        f"/events/{draft_event['id']}",
        json={"sale_starts_at": "2099-01-01T00:00:00Z"},
        headers=organizer_headers,
    )

    assert response.status_code == 422


async def test_seatmap_groups_seats_by_section_and_row(
    published_event: dict[str, Any], client: AsyncClient
) -> None:
    response = await client.get(f"/events/{published_event['id']}/seatmap")

    body = response.json()
    assert body["event_id"] == published_event["id"]
    assert [section["name"] for section in body["sections"]] == ["Orchestra", "Balcony"]

    orchestra = body["sections"][0]
    assert [row["label"] for row in orchestra["rows"]] == ["A", "B"]
    assert [seat["number"] for seat in orchestra["rows"][0]["seats"]] == [1, 2, 3]


async def test_seatmap_prices_seats_by_tier(
    published_event: dict[str, Any], client: AsyncClient
) -> None:
    response = await client.get(f"/events/{published_event['id']}/seatmap")

    body = response.json()
    tiers = {tier["id"]: tier["name"] for tier in body["price_tiers"]}
    orchestra = next(s for s in body["sections"] if s["name"] == "Orchestra")
    row_a = next(row for row in orchestra["rows"] if row["label"] == "A")
    row_b = next(row for row in orchestra["rows"] if row["label"] == "B")

    assert {tiers[seat["price_tier_id"]] for seat in row_a["seats"]} == {"Gold"}
    assert {tiers[seat["price_tier_id"]] for seat in row_b["seats"]} == {"Silver"}


async def test_seatmap_of_draft_is_hidden_from_anonymous_users(
    draft_event: dict[str, Any], client: AsyncClient
) -> None:
    response = await client.get(f"/events/{draft_event['id']}/seatmap")

    assert response.status_code == 404
