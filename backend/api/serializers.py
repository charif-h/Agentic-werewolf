"""What the API shows to clients (no hidden information)"""
from backend.config import get_settings
from backend.game.game_logic import WerewolfGame
from backend.models.game_models import PlayerProfile, PlayerStatus


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


def public_phase_result(game: WerewolfGame, result: dict) -> dict:
    """A phase result with the night results reduced to what everyone may see"""
    if "night_results" not in result:
        return result
    return {**result, "night_results": public_night_results(game, result["night_results"])}
