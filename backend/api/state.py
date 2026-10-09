"""Shared server state: running games and WebSocket connections"""
import logging
from typing import Dict, List

from fastapi import WebSocket

from backend.config import get_settings
from backend.services.sessions import SessionManager

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections, grouped by game id"""

    def __init__(self):
        self.connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, game_id: str, websocket: WebSocket):
        await websocket.accept()
        self.connections.setdefault(game_id, []).append(websocket)

    def disconnect(self, game_id: str, websocket: WebSocket):
        sockets = self.connections.get(game_id, [])
        if websocket in sockets:
            sockets.remove(websocket)
        if not sockets:
            self.connections.pop(game_id, None)

    async def broadcast(self, game_id: str, message: dict):
        """Send a message to every client watching this game"""
        for connection in list(self.connections.get(game_id, [])):
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning("Error broadcasting: %s", e)


# All running games, by id. Routers read these through this module (`state.sessions`)
# so tests can replace them.
sessions = SessionManager(
    ttl_seconds=get_settings().session_ttl_minutes * 60,
    max_sessions=get_settings().max_sessions,
)
manager = ConnectionManager()
