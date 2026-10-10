from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from httpx import AsyncClient

from src.auth.security import ALGORITHM, create_access_token
from src.config import get_settings


async def test_me_returns_current_user(
    registered_attendee: dict[str, str],
    attendee_tokens: dict[str, str],
    client: AsyncClient,
) -> None:
    response = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {attendee_tokens['access_token']}"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == registered_attendee["id"]
    assert response.json()["email"] == registered_attendee["email"]


async def test_me_rejects_missing_token(client: AsyncClient) -> None:
    response = await client.get("/auth/me")

    assert response.status_code == 401


async def test_me_rejects_garbage_token(client: AsyncClient) -> None:
    response = await client.get(
        "/auth/me", headers={"Authorization": "Bearer not-a-token"}
    )

    assert response.status_code == 401


async def test_me_rejects_refresh_token_used_as_access_token(
    attendee_tokens: dict[str, str], client: AsyncClient
) -> None:
    response = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {attendee_tokens['refresh_token']}"},
    )

    assert response.status_code == 401


async def test_me_rejects_expired_token(
    registered_attendee: dict[str, str], client: AsyncClient
) -> None:
    settings = get_settings()
    issued_at = datetime.now(UTC) - timedelta(hours=2)
    expired = jwt.encode(
        {
            "sub": registered_attendee["id"],
            "type": "access",
            "iat": issued_at,
            "exp": issued_at + timedelta(minutes=15),
        },
        settings.jwt_secret_key,
        algorithm=ALGORITHM,
    )

    response = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {expired}"}
    )

    assert response.status_code == 401


async def test_me_rejects_token_signed_with_another_key(
    registered_attendee: dict[str, str], client: AsyncClient
) -> None:
    forged = jwt.encode(
        {
            "sub": registered_attendee["id"],
            "type": "access",
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(minutes=15),
        },
        "an attacker key long enough to avoid a weak key warning",
        algorithm="HS256",
    )

    response = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {forged}"}
    )

    assert response.status_code == 401


async def test_me_rejects_valid_token_for_deleted_user(client: AsyncClient) -> None:
    orphan = create_access_token(uuid4())

    response = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {orphan}"}
    )

    assert response.status_code == 401
