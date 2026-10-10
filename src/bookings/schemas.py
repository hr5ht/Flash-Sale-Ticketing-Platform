from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class HoldState(StrEnum):
    active = "active"
    expired = "expired"
    released = "released"
    confirmed = "confirmed"


class SeatAvailability(StrEnum):
    available = "available"
    held = "held"
    booked = "booked"


class HoldCreate(BaseModel):
    seat_ids: list[int] = Field(min_length=1, max_length=50)


class HoldRead(BaseModel):
    id: int
    event_id: int
    seat_ids: list[int]
    state: HoldState
    expires_at: datetime
    created_at: datetime


class BookingRead(BaseModel):
    id: int
    event_id: int
    hold_id: int
    seat_ids: list[int]
    total_cents: int
    created_at: datetime


class SalesSummary(BaseModel):
    event_id: int
    seats_total: int
    seats_booked: int
    seats_held: int
    seats_available: int
    bookings: int
    gross_cents: int
