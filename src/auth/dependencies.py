from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.exceptions import InsufficientRole, InvalidToken
from src.auth.models import Role, User
from src.auth.security import decode_token
from src.database import get_session

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    if credentials is None:
        raise InvalidToken
    user_id = decode_token(credentials.credentials, "access")
    user = await session.get(User, user_id)
    if user is None:
        raise InvalidToken
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_optional_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User | None:
    if credentials is None:
        return None
    return await get_current_user(credentials, session)


OptionalUser = Annotated[User | None, Depends(get_optional_user)]


async def require_organizer(user: CurrentUser) -> User:
    if user.role not in (Role.organizer, Role.admin):
        raise InsufficientRole
    return user
