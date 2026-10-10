from fastapi import status

from src.exceptions import AppError


class EventNotFound(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "event not found"


class NotEventOwner(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    detail = "event belongs to another organizer"


class EventNotEditable(AppError):
    status_code = status.HTTP_409_CONFLICT
    detail = "a published event cannot be edited"


class EventAlreadyPublished(AppError):
    status_code = status.HTTP_409_CONFLICT
    detail = "event is already published"


class InvalidEventSchedule(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    detail = "sale_starts_at must not be after starts_at"
