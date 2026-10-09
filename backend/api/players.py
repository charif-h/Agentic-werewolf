"""Player information of a game"""
from fastapi import APIRouter

from backend.api.deps import get_session
from backend.api.serializers import serialize_player

router = APIRouter(prefix="/api/games/{game_id}/players", tags=["players"])


@router.get("")
async def get_players(game_id: str):
    """Get all player profiles"""
    game = get_session(game_id).game
    return {
        "players": [serialize_player(p, detailed=True) for p in game.state.players]
    }
