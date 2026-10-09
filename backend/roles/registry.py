"""Registry of role handlers, keyed by `Role`"""
from typing import Dict, List, Optional, Type

from backend.models.game_models import Role
from backend.roles.base import RoleHandler

_HANDLERS: Dict[Role, RoleHandler] = {}


def register(handler_class: Type[RoleHandler]) -> Type[RoleHandler]:
    """Class decorator: instantiate the handler and register it for its role"""
    _HANDLERS[handler_class.role] = handler_class()
    return handler_class


def get_handler(role: Optional[Role]) -> RoleHandler:
    """Handler for `role`; a missing role is treated as a plain villager"""
    return _HANDLERS[role if role is not None else Role.VILLAGER]


def all_handlers() -> List[RoleHandler]:
    return list(_HANDLERS.values())


def night_handlers() -> List[RoleHandler]:
    """Handlers of roles that act at night, in the order they act"""
    return sorted((h for h in _HANDLERS.values() if h.acts_at_night),
                  key=lambda h: h.night_order)
