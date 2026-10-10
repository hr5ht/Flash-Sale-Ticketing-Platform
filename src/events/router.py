from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from src.auth.dependencies import require_organizer
from src.auth.models import User
from src.database import SessionDep
from src.events.dependencies import ManagedEvent, VisibleEvent
from src.events.models import EventStatus
from src.events.schemas import (
    EventCreate,
    EventDetail,
    EventQuery,
    EventSummary,
    EventUpdate,
    SeatMapRead,
)
from src.events.service import (
    create_event,
    get_seat_map,
    list_events,
    publish_event,
    update_event,
)
from src.pagination import Page

router = APIRouter(prefix="/events", tags=["events"])

QueryDep = Annotated[EventQuery, Query()]
Organizer = Annotated[User, Depends(require_organizer)]


@router.post("", response_model=EventDetail, status_code=status.HTTP_201_CREATED)
async def create(
    payload: EventCreate, organizer: Organizer, session: SessionDep
) -> EventDetail:
    event = await create_event(session, organizer, payload)
    return EventDetail.model_validate(event)


@router.get("", response_model=Page[EventSummary])
async def list_published(query: QueryDep, session: SessionDep) -> Page[EventSummary]:
    return await list_events(session, query, status=EventStatus.published)


@router.get("/mine", response_model=Page[EventSummary])
async def list_mine(
    query: QueryDep, organizer: Organizer, session: SessionDep
) -> Page[EventSummary]:
    return await list_events(session, query, organizer=organizer)


@router.get("/{event_id}", response_model=EventDetail)
async def detail(event: VisibleEvent) -> EventDetail:
    return EventDetail.model_validate(event)


@router.patch("/{event_id}", response_model=EventDetail)
async def update(
    payload: EventUpdate, event: ManagedEvent, session: SessionDep
) -> EventDetail:
    updated = await update_event(session, event, payload)
    return EventDetail.model_validate(updated)


@router.post("/{event_id}/publish", response_model=EventDetail)
async def publish(event: ManagedEvent, session: SessionDep) -> EventDetail:
    published = await publish_event(session, event)
    return EventDetail.model_validate(published)


@router.get("/{event_id}/seatmap", response_model=SeatMapRead)
async def seat_map(event: VisibleEvent, session: SessionDep) -> SeatMapRead:
    return await get_seat_map(session, event)
