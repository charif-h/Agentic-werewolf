"""Create, inspect and play games"""
import asyncio
import logging
from typing import Set

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.api import state
from backend.api.deps import acquire, get_session
from backend.api.serializers import public_phase_result, serialize_player
from backend.config import get_settings
from backend.game.game_logic import WerewolfGame
from backend.llm.factory import create_llm_client
from backend.llm.health import check_model
from backend.models.game_models import GamePhase
from backend.services.phases import advance_phase
from backend.services.sessions import GameSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/games", tags=["games"])

# Keeps references to background phases so they are not garbage collected
_background_tasks: Set[asyncio.Task] = set()


class GameRequest(BaseModel):
    """Request model for creating a game"""
    num_players: int = Field(default_factory=lambda: get_settings().default_players, ge=1, le=1000)


@router.post("")
async def create_game(request: GameRequest):
    """
    Create a new game and return its id

    Args:
        request: Game creation request with num_players
    """
    # Limit the number of players: every one of them is a model call
    settings = get_settings()
    num_players = max(settings.min_players, min(request.num_players, settings.max_players))

    llm = create_llm_client()
    ready, message = await asyncio.to_thread(check_model, llm)
    if not ready:
        raise HTTPException(status_code=503, detail=message)

    game = WerewolfGame(num_players=num_players, llm=llm)
    game_state = await asyncio.to_thread(game.setup_game)
    session = state.sessions.create(game)

    return JSONResponse({
        "status": "success",
        "message": "Game created successfully",
        "game_id": session.id,
        "game_state": {
            "num_players": len(game_state.players),
            "phase": game_state.phase.value
        }
    })


@router.delete("/{game_id}")
async def delete_game(game_id: str):
    """Delete a game"""
    if not state.sessions.delete(game_id):
        raise HTTPException(status_code=404, detail="Game not found")
    return {"status": "success"}


@router.get("/{game_id}")
async def get_game_state(game_id: str):
    """Get current game state"""
    session = get_session(game_id)
    game_state = session.game.state
    return {
        "game_id": game_id,
        "phase": game_state.phase.value,
        "day_number": game_state.day_number,
        "players": [serialize_player(p) for p in game_state.players],
        "game_log": game_state.game_log[-20:],  # Last 20 entries
        "llm": session.game.metrics.snapshot(),  # model calls, tokens and time of this game
    }


@router.post("/{game_id}/start")
async def start_game(game_id: str):
    """Start the game (begin first night)"""
    session = get_session(game_id)
    acquire(session)
    try:
        announcement = session.game.start_night()
    finally:
        session.lock.release()

    await state.manager.broadcast(game_id, {
        "type": "phase_change",
        "data": {
            "phase": "night",
            "day_number": session.game.state.day_number,
            "announcement": announcement
        }
    })
    return {"status": "success", "announcement": announcement}


async def _play_phase(game_id: str, session: GameSession) -> dict:
    """
    Play the current phase in a worker thread so the server stays responsive.
    Progress events (player_spoke, vote_cast) are broadcast while it runs and
    a final phase_change when it ends. The caller must hold the session lock;
    it is released here.
    """
    loop = asyncio.get_running_loop()
    game = session.game

    def emit(event_type: str, data: dict) -> None:
        """Called from the worker thread"""
        asyncio.run_coroutine_threadsafe(
            state.manager.broadcast(game_id, {"type": event_type, "data": data}), loop
        )

    game.on_event = emit
    try:
        result = public_phase_result(game, await asyncio.to_thread(advance_phase, game))
        await state.manager.broadcast(game_id, {"type": "phase_change", "data": result})
        if result.get("game_ended"):
            await state.manager.broadcast(game_id, {"type": "game_ended", "data": {
                "winner": result.get("winner"), "announcement": result.get("end_announcement"),
            }})
        return result
    finally:
        game.on_event = None
        session.lock.release()


async def _play_phase_in_background(game_id: str, session: GameSession) -> None:
    try:
        await _play_phase(game_id, session)
    except Exception:
        logger.exception("Background phase failed for game %s", game_id)
        await state.manager.broadcast(game_id, {
            "type": "error", "data": "Failed to progress to the next phase"
        })


@router.post("/{game_id}/next-phase")
async def next_phase(game_id: str, background: bool = False):
    """
    Progress to the next game phase

    By default the request waits for the phase to finish and returns its result.
    With `background=true` it answers 202 at once and the result arrives on the
    game's WebSocket as a `phase_change` event. Either way, progress events are
    pushed to the WebSocket while the phase is played.
    """
    session = get_session(game_id)
    phase = session.game.state.phase
    if phase == GamePhase.SETUP:
        raise HTTPException(status_code=409, detail="The game has not started yet: POST /start first")
    if phase == GamePhase.ENDED:
        raise HTTPException(status_code=409, detail="The game has ended")
    acquire(session)

    if background:
        task = asyncio.create_task(_play_phase_in_background(game_id, session))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
        return JSONResponse(status_code=202, content={"status": "started"})

    return {"status": "success", "data": await _play_phase(game_id, session)}
