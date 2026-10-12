"""Player information of a game"""
from fastapi import APIRouter, HTTPException

from backend.api.deps import get_session
from backend.api.serializers import diary_visible, serialize_player

router = APIRouter(prefix="/api/games/{game_id}/players", tags=["players"])


@router.get("")
async def get_players(game_id: str):
    """Get all player profiles"""
    game = get_session(game_id).game
    return {
        "players": [serialize_player(p, detailed=True) for p in game.state.players]
    }


@router.get("/{player_id}/diary")
async def get_diary(game_id: str, player_id: str):
    """
    The private diary of a player, one entry per night and day. It reveals the player's
    secret thoughts, so it follows the rule of roles: shown with REVEAL_ROLES, for
    eliminated players, and once the game has ended.
    """
    game = get_session(game_id).game
    agent = game.player_agents.get(player_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Player not found")
    if not diary_visible(agent.profile, game):
        raise HTTPException(status_code=403, detail="The diary of a living player is secret")
    return {"player": agent.profile.name, "entries": agent.diary}
