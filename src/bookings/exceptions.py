from fastapi import status

from src.exceptions import AppError


class SeatsUnavailable(AppError):
    status_code = status.HTTP_409_CONFLICT
    detail = "one or more seats are already held or booked"


class SeatsNotInEvent(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    detail = "one or more seats do not belong to this event"


class SeatLimitExceeded(AppError):
    status_code = status.HTTP_409_CONFLICT
    detail = "seat limit for this event would be exceeded"


class SaleNotStarted(AppError):
    status_code = status.HTTP_409_CONFLICT
    detail = "the sale for this event has not started"


class EventNotOnSale(AppError):
    status_code = status.HTTP_409_CONFLICT
    detail = "the event is not published"


class HoldNotFound(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "hold not found"


class HoldNotActive(AppError):
    status_code = status.HTTP_409_CONFLICT
    detail = "hold is no longer active"


class BookingNotFound(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "booking not found"
