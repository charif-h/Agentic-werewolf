from typing import Dict, List

from backend.models.game_models import GameState, PlayerProfile, Role
from backend.roles.base import RoleHandler, alive_names
from backend.roles.registry import register


@register
class Seer(RoleHandler):
    role = Role.SEER

    description = ("You are the SEER. Each night, you can discover the true identity of one player. "
                   "Use this information wisely during day discussions without revealing your role.")
    discussion_strategy = """You can see true identities at night.
- Use your knowledge subtly
- Don't reveal your role unless necessary
- Guide discussions toward confirmed werewolves"""
    response_hint = ("- As someone with special knowledge, consider if you should "
                     "guide the discussion")

    night_order = 30
    night_instruction = "As the seer, choose a player whose identity you want to reveal"

    def night_targets(self, state: GameState, actor: PlayerProfile) -> List[str]:
        return alive_names(state, exclude=actor.id)

    def record_night(self, results: Dict, target: PlayerProfile) -> None:
        results['seer_check'] = {'player': target.name, 'role': target.role.value}
