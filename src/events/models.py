from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class EventStatus(StrEnum):
    draft = "draft"
    published = "published"


class EventCategory(StrEnum):
    concert = "concert"
    sports = "sports"
    theatre = "theatre"
    conference = "conference"
    festival = "festival"


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("sale_starts_at <= starts_at", name="ck_events_sale_before_start"),
        Index("ix_events_organizer_id", "organizer_id"),
        Index("ix_events_status_starts_at", "status", "starts_at"),
        Index("ix_events_status_category_starts_at", "status", "category", "starts_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    organizer_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[EventCategory] = mapped_column(
        Enum(EventCategory, name="event_category")
    )
    city: Mapped[str] = mapped_column(Text)
    venue: Mapped[str] = mapped_column(Text)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sale_starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[EventStatus] = mapped_column(
        Enum(EventStatus, name="event_status"), server_default=EventStatus.draft.value
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    price_tiers: Mapped[list["PriceTier"]] = relationship(
        back_populates="event", cascade="all, delete-orphan", order_by="PriceTier.price_cents"
    )
    sections: Mapped[list["Section"]] = relationship(
        back_populates="event", cascade="all, delete-orphan", order_by="Section.name"
    )


Index(
    "ix_events_status_city_starts_at",
    Event.status,
    func.lower(Event.city),
    Event.starts_at,
)


class PriceTier(Base):
    __tablename__ = "price_tiers"
    __table_args__ = (
        CheckConstraint("price_cents > 0", name="ck_price_tiers_price_positive"),
        UniqueConstraint("event_id", "name", name="uq_price_tiers_event_name"),
        UniqueConstraint("id", "event_id", name="uq_price_tiers_id_event"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    event_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("events.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(Text)
    price_cents: Mapped[int] = mapped_column(Integer)

    event: Mapped[Event] = relationship(back_populates="price_tiers")


class Section(Base):
    __tablename__ = "sections"
    __table_args__ = (
        UniqueConstraint("event_id", "name", name="uq_sections_event_name"),
        UniqueConstraint("id", "event_id", name="uq_sections_id_event"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    event_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("events.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(Text)

    event: Mapped[Event] = relationship(back_populates="sections")


class Seat(Base):
    __tablename__ = "seats"
    __table_args__ = (
        ForeignKeyConstraint(
            ["section_id", "event_id"],
            ["sections.id", "sections.event_id"],
            ondelete="CASCADE",
            name="fk_seats_section_event",
        ),
        ForeignKeyConstraint(
            ["price_tier_id", "event_id"],
            ["price_tiers.id", "price_tiers.event_id"],
            ondelete="CASCADE",
            name="fk_seats_price_tier_event",
        ),
        UniqueConstraint(
            "section_id", "row_label", "seat_number", name="uq_seats_section_row_number"
        ),
        Index("ix_seats_event_id", "event_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    event_id: Mapped[int] = mapped_column(BigInteger)
    section_id: Mapped[int] = mapped_column(BigInteger)
    price_tier_id: Mapped[int] = mapped_column(BigInteger)
    row_label: Mapped[str] = mapped_column(Text)
    seat_number: Mapped[int] = mapped_column(Integer)
