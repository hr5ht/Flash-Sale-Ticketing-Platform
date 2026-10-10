from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class HoldStatus(StrEnum):
    active = "active"
    released = "released"
    confirmed = "confirmed"


class Hold(Base):
    __tablename__ = "holds"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "idempotency_key", name="uq_holds_user_idempotency_key"
        ),
        Index("ix_holds_event_user", "event_id", "user_id"),
        Index("ix_holds_status_expires_at", "status", "expires_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    event_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("events.id", ondelete="CASCADE")
    )
    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    status: Mapped[HoldStatus] = mapped_column(
        Enum(HoldStatus, name="hold_status"), server_default=HoldStatus.active.value
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SeatClaim(Base):
    __tablename__ = "seat_claims"
    __table_args__ = (Index("ix_seat_claims_hold_id", "hold_id"),)

    seat_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("seats.id", ondelete="CASCADE"), primary_key=True
    )
    hold_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("holds.id", ondelete="CASCADE")
    )


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("total_cents > 0", name="ck_bookings_total_positive"),
        UniqueConstraint("hold_id", name="uq_bookings_hold"),
        UniqueConstraint(
            "user_id", "idempotency_key", name="uq_bookings_user_idempotency_key"
        ),
        Index("ix_bookings_event_id", "event_id"),
        Index("ix_bookings_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    event_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("events.id", ondelete="CASCADE")
    )
    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    hold_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("holds.id", ondelete="CASCADE")
    )
    total_cents: Mapped[int] = mapped_column(Integer)
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
