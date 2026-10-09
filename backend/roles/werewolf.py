from typing import Dict, List

from backend.models.game_models import GameState, PlayerProfile, PlayerStatus, Role
from backend.roles.base import WEREWOLVES, RoleHandler
from backend.roles.registry import register


@register
class Werewolf(RoleHandler):
    role = Role.WEREWOLF
    team = WEREWOLVES

    description = ("You are a WEREWOLF. Your goal is to eliminate villagers without being discovered. "
                   "During the night, you coordinate with other werewolves to choose a victim. "
                   "During the day, you must blend in and deflect suspicion.")
    discussion_strategy = """Your goal: eliminate villagers without being discovered.
- Act like a concerned villager
- Subtly redirect suspicion onto others
- Don't defend other werewolves obviously"""
    voting_strategy = """As a WEREWOLF, vote to eliminate:
1. Confirmed or suspected special roles (seer, witch, etc.)
2. The most active and influential villagers
3. Anyone who has been suspicious of werewolves
4. Avoid voting for fellow werewolves unless absolutely necessary"""
    response_hint = "- Consider if you need to deflect suspicion or redirect attention"

    night_order = 10
    night_instruction = "As a werewolf, choose one villager to eliminate tonight"
    night_constraint = " You cannot target other werewolves."
    announce_night_choice = True

    def night_targets(self, state: GameState, actor: PlayerProfile) -> List[str]:
        return [p.name for p in state.players
                if p.status == PlayerStatus.ALIVE and p.role != Role.WEREWOLF]

    def record_night(self, results: Dict, target: PlayerProfile) -> None:
        if target.role != Role.WEREWOLF:
            results['killed'] = target.id
