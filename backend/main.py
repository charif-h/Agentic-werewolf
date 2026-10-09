"""
FastAPI Backend for Werewolves of Millers Hollow
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Dict, List, Optional
import json
import logging
from pydantic import BaseModel, Field

from backend.config import get_settings
from backend.game.game_logic import WerewolfGame
from backend.agents.ai_provider import AIProvider
from backend.models.game_models import GamePhase, PlayerProfile, PlayerStatus
from backend.services.sessions import GameSession, SessionManager, SessionNotFound

logger = logging.getLogger(__name__)

app = FastAPI(title="Werewolves of Millers Hollow API")

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=False,  # the API uses no cookies
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)

# All running games, by id
sessions = SessionManager(
    ttl_seconds=get_settings().session_ttl_minutes * 60,
    max_sessions=get_settings().max_sessions,
)


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


manager = ConnectionManager()


def serialize_player(player: PlayerProfile, detailed: bool = False) -> dict:
    """
    Public view of a player. The role is only included when REVEAL_ROLES is on
    or the player is dead, so the API does not spoil the game.
    """
    data = {
        "id": player.id,
        "name": player.name,
        "sex": player.sex.value,
        "age": player.age,
        "personality": player.personality.value,
        "status": player.status.value,
        "role": None,
    }
    if detailed:
        data["personality_description"] = player.get_personality_description()
    if player.role and (get_settings().reveal_roles or player.status == PlayerStatus.DEAD):
        data["role"] = player.role.value
    return data


def public_night_results(game: WerewolfGame, results: dict) -> dict:
    """Night results safe to send to every client (no guard or seer information)"""
    if get_settings().reveal_roles:
        return results
    dead_ids = list(results.get('deaths', [])) + [target for _, target in results.get('hunter_shots', [])]
    names = [p.name for pid in dead_ids for p in game.state.players if p.id == pid]
    return {"deaths": names}


def server_error(action: str) -> HTTPException:
    """Log the active exception and return a generic 500 (no internal details)"""
    logger.exception("Error while trying to %s", action)
    return HTTPException(status_code=500, detail=f"Failed to {action}")


def get_session(game_id: str) -> GameSession:
    """The session for `game_id`, or a 404"""
    try:
        return sessions.get(game_id)
    except SessionNotFound:
        raise HTTPException(status_code=404, detail="Game not found")


def acquire(session: GameSession) -> None:
    """Take the session lock or answer 409 if a phase is already running"""
    if not session.lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="This game is busy playing a phase")


@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "name": "Werewolves of Millers Hollow API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/api/providers")
async def get_providers():
    """Get available AI providers"""
    try:
        providers = AIProvider.get_available_providers()
        return {"providers": providers}
    except Exception:
        # Don't expose internal error details
        return {"providers": [], "error": "Failed to load AI providers"}


class GameRequest(BaseModel):
    """Request model for creating a game"""
    num_players: int = Field(default_factory=lambda: get_settings().default_players, ge=1, le=1000)
    ai_provider: Optional[str] = None


@app.post("/api/games")
async def create_game(request: GameRequest):
    """
    Create a new game and return its id

    Args:
        request: Game creation request with num_players and ai_provider
    """
    try:
        # Limit players to reduce API calls and avoid rate limits
        settings = get_settings()
        num_players = max(settings.min_players, min(request.num_players, settings.max_players))

        game = WerewolfGame(num_players=num_players, ai_provider=request.ai_provider)
        state = game.setup_game()
        session = sessions.create(game)

        return JSONResponse({
            "status": "success",
            "message": "Game created successfully",
            "game_id": session.id,
            "game_state": {
                "num_players": len(state.players),
                "phase": state.phase.value
            }
        })
    except Exception:
        raise server_error("create game")


@app.delete("/api/games/{game_id}")
async def delete_game(game_id: str):
    """Delete a game"""
    if not sessions.delete(game_id):
        raise HTTPException(status_code=404, detail="Game not found")
    return {"status": "success"}


@app.get("/api/games/{game_id}")
async def get_game_state(game_id: str):
    """Get current game state"""
    state = get_session(game_id).game.state
    return {
        "game_id": game_id,
        "phase": state.phase.value,
        "day_number": state.day_number,
        "players": [serialize_player(p) for p in state.players],
        "game_log": state.game_log[-20:]  # Last 20 entries
    }


@app.post("/api/games/{game_id}/start")
async def start_game(game_id: str):
    """Start the game (begin first night)"""
    session = get_session(game_id)
    game = session.game
    acquire(session)
    try:
        announcement = game.start_night()

        await manager.broadcast(game_id, {
            "type": "phase_change",
            "data": {
                "phase": "night",
                "day_number": game.state.day_number,
                "announcement": announcement
            }
        })

        return {"status": "success", "announcement": announcement}
    except Exception:
        raise server_error("start game")
    finally:
        session.lock.release()


@app.post("/api/games/{game_id}/next-phase")
async def next_phase(game_id: str):
    """Progress to next game phase"""
    session = get_session(game_id)
    game = session.game
    acquire(session)
    try:
        current_phase = game.state.phase
        result = {}

        if current_phase.value == "night":
            # Process night actions and move to day
            night_results = game.process_night_actions()
            announcement = game.start_day()
            result = {
                "phase": "day",
                "announcement": announcement,
                "night_results": public_night_results(game, night_results)
            }

        elif current_phase.value == "day":
            # Start discussion (dynamic multi-round discussion)
            game.state.phase = GamePhase.DISCUSSION
            messages = game.conduct_discussion()
            result = {
                "phase": "discussion",
                "messages": messages
            }

        elif current_phase.value == "discussion":
            # Conduct vote
            eliminated, votes = game.conduct_vote()
            result = {
                "phase": "voting",
                "eliminated": eliminated.name if eliminated else None,
                "votes": votes
            }

            # Check win condition
            winner = game.check_win_condition()
            if winner:
                end_announcement = game.end_game(winner)
                result["game_ended"] = True
                result["winner"] = winner
                result["end_announcement"] = end_announcement
            else:
                # Start next night
                night_announcement = game.start_night()
                result["next_phase"] = "night"
                result["night_announcement"] = night_announcement

        elif current_phase.value == "voting":
            # After voting, check win condition and continue
            winner = game.check_win_condition()
            if winner:
                end_announcement = game.end_game(winner)
                result = {
                    "phase": "ended",
                    "game_ended": True,
                    "winner": winner,
                    "end_announcement": end_announcement
                }
            else:
                # Start next night
                night_announcement = game.start_night()
                result = {
                    "phase": "night",
                    "night_announcement": night_announcement
                }

        else:
            # Handle unexpected phases
            result = {"error": f"Unknown phase: {current_phase.value}"}

        await manager.broadcast(game_id, {
            "type": "phase_change",
            "data": result
        })

        return {"status": "success", "data": result}
    except Exception:
        raise server_error("progress to the next phase")
    finally:
        session.lock.release()


@app.get("/api/games/{game_id}/players")
async def get_players(game_id: str):
    """Get all player profiles"""
    game = get_session(game_id).game
    return {
        "players": [serialize_player(p, detailed=True) for p in game.state.players]
    }


@app.websocket("/ws/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str):
    """WebSocket endpoint for real-time updates of one game"""
    if sessions.find(game_id) is None:
        await websocket.close(code=4404)  # unknown game
        return
    await manager.connect(game_id, websocket)
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
        manager.disconnect(game_id, websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=get_settings().host, port=get_settings().port)
