from httpx import AsyncClient


async def test_refresh_returns_new_access_token(
    attendee_tokens: dict[str, str], client: AsyncClient
) -> None:
    response = await client.post(
        "/auth/refresh", json={"refresh_token": attendee_tokens["refresh_token"]}
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


async def test_refreshed_access_token_authenticates(
    registered_attendee: dict[str, str],
    attendee_tokens: dict[str, str],
    client: AsyncClient,
) -> None:
    refreshed = await client.post(
        "/auth/refresh", json={"refresh_token": attendee_tokens["refresh_token"]}
    )
    access_token = refreshed.json()["access_token"]

    response = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {access_token}"}
    )

    assert response.status_code == 200
    assert response.json()["id"] == registered_attendee["id"]


async def test_refresh_rejects_access_token(
    attendee_tokens: dict[str, str], client: AsyncClient
) -> None:
    response = await client.post(
        "/auth/refresh", json={"refresh_token": attendee_tokens["access_token"]}
    )

    assert response.status_code == 401


async def test_refresh_rejects_garbage_token(client: AsyncClient) -> None:
    response = await client.post("/auth/refresh", json={"refresh_token": "nonsense"})

    assert response.status_code == 401
