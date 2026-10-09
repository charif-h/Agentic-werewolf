from backend.models.game_models import Role
from backend.roles.base import RoleHandler
from backend.roles.registry import register


@register
class Witch(RoleHandler):
    role = Role.WITCH

    description = ("You are the WITCH. You have two potions: one to save someone from death, "
                   "and one to kill someone. You can use each potion only once during the game.")
    discussion_strategy = """You have healing and poison potions.
- Keep your role secret
- Use night action knowledge carefully
- Observe who might know too much"""
    response_hint = "- Consider if you can help identify threats"

    # The witch does not pick a single target like the other night roles: the
    # game asks her to save the werewolves' victim and/or poison someone
    # (see WerewolfGame._witch_decision), so she has no `night_order`.
