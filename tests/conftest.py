from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config import get_settings
from src.database import Base, get_session, session_dependency
from src.main import app


@pytest.fixture(scope="session")
async def engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(
        get_settings().test_database_url, pool_size=30, max_overflow=10
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def connection(engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        yield connection
        await transaction.rollback()


@pytest.fixture
async def session(connection: AsyncConnection) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    async with factory() as session:
        yield session


@pytest.fixture
async def client(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    app.dependency_overrides[get_session] = lambda: session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
async def registered_attendee(client: AsyncClient) -> dict[str, str]:
    email = "ada@example.com"
    password = "correct horse"
    response = await client.post(
        "/auth/register", json={"email": email, "password": password}
    )
    return {"id": response.json()["id"], "email": email, "password": password}


@pytest.fixture
async def registered_organizer(client: AsyncClient) -> dict[str, str]:
    email = "grace@example.com"
    password = "correct horse"
    response = await client.post(
        "/auth/register",
        json={"email": email, "password": password, "role": "organizer"},
    )
    return {"id": response.json()["id"], "email": email, "password": password}


@pytest.fixture
async def attendee_tokens(
    registered_attendee: dict[str, str], client: AsyncClient
) -> dict[str, str]:
    response = await client.post(
        "/auth/login",
        json={
            "email": registered_attendee["email"],
            "password": registered_attendee["password"],
        },
    )
    return response.json()


TABLES = "users, events, price_tiers, sections, seats, holds, seat_claims, bookings"


@asynccontextmanager
async def committing_client(engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    app.dependency_overrides[get_session] = session_dependency(factory)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))


@pytest.fixture
async def committed_client(engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    async with committing_client(engine) as client:
        yield client


@pytest.fixture
async def organizer_headers(
    registered_organizer: dict[str, str], client: AsyncClient
) -> dict[str, str]:
    response = await client.post(
        "/auth/login",
        json={
            "email": registered_organizer["email"],
            "password": registered_organizer["password"],
        },
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
async def attendee_headers(attendee_tokens: dict[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {attendee_tokens['access_token']}"}
