from typing import Any

from httpx import AsyncClient
from sqlalchemy import event as sqlalchemy_event

from tests.events.conftest import event_payload


def count_selects(connection) -> list[str]:
    statements: list[str] = []

    def record(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    sqlalchemy_event.listen(connection.sync_connection, "before_cursor_execute", record)
    return statements


async def test_listing_many_events_uses_a_constant_number_of_queries(
    organizer_headers: dict[str, str], client: AsyncClient, connection
) -> None:
    for index in range(5):
        created = await client.post(
            "/events",
            json=event_payload(title=f"Event {index}"),
            headers=organizer_headers,
        )
        await client.post(
            f"/events/{created.json()['id']}/publish", headers=organizer_headers
        )

    statements = count_selects(connection)
    response = await client.get("/events")

    assert response.json()["total"] == 5
    assert len(statements) == 2


async def test_seatmap_uses_a_constant_number_of_queries(
    published_event: dict[str, Any], client: AsyncClient, connection
) -> None:
    statements = count_selects(connection)
    response = await client.get(f"/events/{published_event['id']}/seatmap")

    assert response.status_code == 200
    assert len(statements) == 4
