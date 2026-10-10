from datetime import datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from src.bookings.schemas import SeatAvailability
from src.events.models import EventCategory, EventStatus
from src.pagination import PageParams

MAX_SEATS_PER_EVENT = 5000


class PriceTierCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    price_cents: int = Field(gt=0)


class RowCreate(BaseModel):
    label: str = Field(min_length=1, max_length=10)
    seat_count: int = Field(ge=1, le=200)
    price_tier: str


class SectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    rows: list[RowCreate] = Field(min_length=1)


class EventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(max_length=5000)
    category: EventCategory
    city: str = Field(min_length=1, max_length=100)
    venue: str = Field(min_length=1, max_length=200)
    starts_at: AwareDatetime
    sale_starts_at: AwareDatetime
    price_tiers: list[PriceTierCreate] = Field(min_length=1)
    sections: list[SectionCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def check_layout(self) -> "EventCreate":
        if self.sale_starts_at > self.starts_at:
            raise ValueError("sale_starts_at must not be after starts_at")

        tier_names = [tier.name for tier in self.price_tiers]
        if len(set(tier_names)) != len(tier_names):
            raise ValueError("price tier names must be unique")

        section_names = [section.name for section in self.sections]
        if len(set(section_names)) != len(section_names):
            raise ValueError("section names must be unique")

        for section in self.sections:
            labels = [row.label for row in section.rows]
            if len(set(labels)) != len(labels):
                raise ValueError(f"row labels must be unique within section {section.name}")
            for row in section.rows:
                if row.price_tier not in set(tier_names):
                    raise ValueError(f"unknown price tier {row.price_tier}")

        total_seats = sum(
            row.seat_count for section in self.sections for row in section.rows
        )
        if total_seats > MAX_SEATS_PER_EVENT:
            raise ValueError(f"an event may not exceed {MAX_SEATS_PER_EVENT} seats")

        return self


class EventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    category: EventCategory | None = None
    city: str | None = Field(default=None, min_length=1, max_length=100)
    venue: str | None = Field(default=None, min_length=1, max_length=200)
    starts_at: AwareDatetime | None = None
    sale_starts_at: AwareDatetime | None = None


class PriceTierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    price_cents: int


class EventSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    category: EventCategory
    city: str
    venue: str
    starts_at: datetime
    sale_starts_at: datetime
    status: EventStatus
    min_price_cents: int


class EventDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    category: EventCategory
    city: str
    venue: str
    starts_at: datetime
    sale_starts_at: datetime
    status: EventStatus
    price_tiers: list[PriceTierRead]


class EventQuery(PageParams):
    city: str | None = None
    category: EventCategory | None = None
    starts_after: AwareDatetime | None = None
    starts_before: AwareDatetime | None = None


class SeatRead(BaseModel):
    id: int
    number: int
    price_tier_id: int
    status: SeatAvailability


class SeatRowRead(BaseModel):
    label: str
    seats: list[SeatRead]


class SeatSectionRead(BaseModel):
    id: int
    name: str
    rows: list[SeatRowRead]


class SeatMapRead(BaseModel):
    event_id: int
    price_tiers: list[PriceTierRead]
    sections: list[SeatSectionRead]
