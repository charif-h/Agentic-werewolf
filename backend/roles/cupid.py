from backend.models.game_models import Role
from backend.roles.base import RoleHandler
from backend.roles.registry import register


@register
class Cupid(RoleHandler):
    role = Role.CUPID

    description = ("You are CUPID. On the first night, you choose two players to fall in love. "
                   "If one dies, the other dies of heartbreak.")
    # No night action yet: lovers are not linked (see issue "Implement or drop unfinished roles")
