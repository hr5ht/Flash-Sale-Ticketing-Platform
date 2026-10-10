from typing import Annotated

from fastapi import APIRouter, Header, Query, status

from src.auth.dependencies import CurrentUser
from src.bookings.schemas import BookingRead, HoldCreate, HoldRead, SalesSummary
from src.bookings.service import (
    confirm_hold,
    create_hold,
    get_booking,
    list_bookings,
    release_hold,
    sales_summary,
)
from src.database import SessionDep
from src.events.dependencies import ManagedEvent, VisibleEvent
from src.pagination import Page, PageParams

router = APIRouter(tags=["bookings"])

IdempotencyKey = Annotated[str | None, Header(alias="Idempotency-Key")]
PageDep = Annotated[PageParams, Query()]


@router.post(
    "/events/{event_id}/holds",
    response_model=HoldRead,
    status_code=status.HTTP_201_CREATED,
)
async def hold_seats(
    payload: HoldCreate,
    event: VisibleEvent,
    user: CurrentUser,
    session: SessionDep,
    idempotency_key: IdempotencyKey = None,
) -> HoldRead:
    return await create_hold(session, user, event, payload.seat_ids, idempotency_key)


@router.delete("/holds/{hold_id}", status_code=status.HTTP_204_NO_CONTENT)
async def release(hold_id: int, user: CurrentUser, session: SessionDep) -> None:
    await release_hold(session, user, hold_id)


@router.post("/holds/{hold_id}/confirm", response_model=BookingRead)
async def confirm(
    hold_id: int,
    user: CurrentUser,
    session: SessionDep,
    idempotency_key: IdempotencyKey = None,
) -> BookingRead:
    return await confirm_hold(session, user, hold_id, idempotency_key)


@router.get("/bookings", response_model=Page[BookingRead])
async def my_bookings(
    page: PageDep, user: CurrentUser, session: SessionDep
) -> Page[BookingRead]:
    return await list_bookings(session, user, page)


@router.get("/bookings/{booking_id}", response_model=BookingRead)
async def booking_detail(
    booking_id: int, user: CurrentUser, session: SessionDep
) -> BookingRead:
    return await get_booking(session, user, booking_id)


@router.get("/events/{event_id}/sales", response_model=SalesSummary)
async def event_sales(event: ManagedEvent, session: SessionDep) -> SalesSummary:
    return await sales_summary(session, event)
