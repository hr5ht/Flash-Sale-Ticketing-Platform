from collections.abc import AsyncIterator

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.database import get_session
from src.main import app


async def test_health_reports_ok(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


async def test_health_reports_unavailable_when_database_is_unreachable() -> None:
    unreachable = create_async_engine("postgresql+asyncpg://localhost:5499/flash_sale")
    factory = async_sessionmaker(unreachable, expire_on_commit=False)

    async def failing_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = failing_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    app.dependency_overrides.clear()
    await unreachable.dispose()

    assert response.status_code == 503
