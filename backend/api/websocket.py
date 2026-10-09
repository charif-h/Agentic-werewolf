"""Real-time events of one game"""
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.api import state

router = APIRouter()


@router.websocket("/ws/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str):
    """
    WebSocket endpoint for real-time updates of one game

    Server events: `phase_change`, `player_spoke`, `vote_cast`, `error`.
    Messages sent by the client are echoed back.
    """
    if state.sessions.find(game_id) is None:
        await websocket.close(code=4404)  # unknown game
        return
    await state.manager.connect(game_id, websocket)
    try:
        while True:
            # Keep connection alive and receive messages
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
            except ValueError:
                await websocket.send_json({"type": "error", "data": "Invalid JSON"})
                continue

            # Echo back for now
            await websocket.send_json({
                "type": "echo",
                "data": message
            })
    except WebSocketDisconnect:
        state.manager.disconnect(game_id, websocket)
