from fastapi import WebSocket

connections: dict[int, set[WebSocket]] = {}


def add(event_id: int, websocket: WebSocket) -> None:
    connections.setdefault(event_id, set()).add(websocket)


def remove(event_id: int, websocket: WebSocket) -> None:
    sockets = connections.get(event_id)
    if sockets is None:
        return
    sockets.discard(websocket)
    if not sockets:
        del connections[event_id]
