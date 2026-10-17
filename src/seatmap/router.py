from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.auth.exceptions import InvalidToken
from src.auth.service import user_from_access_token
from src.database import SessionDep
from src.events.exceptions import EventNotFound
from src.events.service import get_seat_map, get_visible_event
from src.seatmap import connections

router = APIRouter()


@router.websocket("/events/{event_id}/seatmap/ws")
async def seat_map_socket(
    websocket: WebSocket,
    event_id: int,
    session: SessionDep,
    token: str | None = None,
) -> None:
    await websocket.accept()
    try:
        viewer = await user_from_access_token(session, token) if token else None
        event = await get_visible_event(session, event_id, viewer)
        seat_map = await get_seat_map(session, event)
    except InvalidToken:
        await websocket.close(code=4401)
        return
    except EventNotFound:
        await websocket.close(code=4404)
        return
    await session.commit()

    connections.add(event_id, websocket)
    try:
        await websocket.send_json(seat_map.model_dump(mode="json"))
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        connections.remove(event_id, websocket)
