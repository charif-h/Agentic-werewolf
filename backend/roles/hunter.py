from backend.models.game_models import Role
from backend.roles.base import RoleHandler
from backend.roles.registry import register


@register
class Hunter(RoleHandler):
    role = Role.HUNTER

    description = ("You are the HUNTER. If you are killed, you can immediately shoot and eliminate "
                   "another player of your choice.")
    discussion_strategy = """If killed, you can eliminate another player.
- Be moderately active to help the village
- Keep a mental list of suspects
- Don't fear taking reasonable risks"""
    response_hint = "- Consider if you can help identify threats"

    death_shot = True
    death_shot_instruction = ("You have just been eliminated. As the hunter, shoot one player "
                              "with your last breath")
