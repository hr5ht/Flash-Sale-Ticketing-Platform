import asyncio

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from src.bookings.models import Booking
from tests.bookings.conftest import count_rows, open_event, register_buyers


async def test_simultaneous_confirms_of_one_hold_create_a_single_booking(
    committed_client: AsyncClient, engine: AsyncEngine
) -> None:
    event_id, seat_ids = await open_event(committed_client, seat_count=1)
    buyers = await register_buyers(committed_client, 1)
    held = await committed_client.post(
        f"/events/{event_id}/holds",
        json={"seat_ids": seat_ids},
        headers=buyers[0],
    )
    hold_id = held.json()["id"]

    responses = await asyncio.gather(
        *(
            committed_client.post(
                f"/holds/{hold_id}/confirm", headers=buyers[0]
            )
            for _ in range(10)
        ),
        return_exceptions=True,
    )

    successes = [
        response
        for response in responses
        if not isinstance(response, BaseException) and response.status_code == 200
    ]
    assert len(successes) == 1
    assert await count_rows(engine, Booking) == 1
