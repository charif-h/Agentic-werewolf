from backend.models.game_models import Role
from backend.roles.base import RoleHandler
from backend.roles.registry import register


@register
class LittleGirl(RoleHandler):
    role = Role.LITTLE_GIRL

    description = ("You are the LITTLE GIRL. You can peek during the werewolf phase at night, "
                   "but risk being caught.")
    # Peeking is not implemented, and the role is never assigned (see issue "Implement or drop unfinished roles")
