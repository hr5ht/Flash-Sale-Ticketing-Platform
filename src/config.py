from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

SeatAcquisitionStrategy = Literal["unique_insert", "for_update", "skip_locked", "upsert"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    test_database_url: str
    jwt_secret_key: str
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    hold_duration_seconds: int = 300
    max_seats_per_user_per_event: int = 6
    seat_acquisition_strategy: SeatAcquisitionStrategy = "upsert"


@lru_cache
def get_settings() -> Settings:
    return Settings()
