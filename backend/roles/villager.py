from backend.models.game_models import Role
from backend.roles.base import VILLAGE_DISCUSSION_STRATEGY, RoleHandler
from backend.roles.registry import register


@register
class Villager(RoleHandler):
    role = Role.VILLAGER

    description = ("You are a VILLAGER. Your goal is to identify and eliminate the werewolves. "
                   "You have no special powers, but you can use logic and observation during discussions.")
    discussion_strategy = VILLAGE_DISCUSSION_STRATEGY
    response_hint = "- Consider if you can help identify threats"
