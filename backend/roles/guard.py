from typing import Dict, List

from backend.models.game_models import GameState, PlayerProfile, PlayerStatus, Role
from backend.roles.base import RoleHandler
from backend.roles.registry import register


@register
class Guard(RoleHandler):
    role = Role.GUARD

    description = ("You are the GUARD. Each night, you can protect one player from werewolf attacks "
                   "(but not the same player twice in a row).")
    discussion_strategy = """You can protect players from attacks.
- Keep protection patterns secret
- Use knowledge of night events subtly
- Look for signs of werewolf coordination"""
    response_hint = "- Consider if you can help identify threats"

    night_order = 20
    night_instruction = "As the guard, choose a player to protect tonight"

    def night_targets(self, state: GameState, actor: PlayerProfile) -> List[str]:
        # The same player cannot be protected two nights in a row
        return [p.name for p in state.players
                if p.status == PlayerStatus.ALIVE and p.id != state.guard_last_protected]

    def record_night(self, results: Dict, target: PlayerProfile) -> None:
        results['protected'] = target.id
