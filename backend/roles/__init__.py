"""
Role handlers, one module per role.

Every module in this package other than `base` and `registry` is imported
automatically, so adding a role means adding one file with a `@register`ed
`RoleHandler` subclass.
"""
import importlib
import pkgutil

from backend.roles.base import RoleHandler, VILLAGERS, WEREWOLVES
from backend.roles.registry import all_handlers, get_handler, night_handlers, register

for _module in pkgutil.iter_modules(__path__):
    if _module.name not in ("base", "registry"):
        importlib.import_module(f"{__name__}.{_module.name}")

__all__ = ["RoleHandler", "VILLAGERS", "WEREWOLVES", "all_handlers", "get_handler",
           "night_handlers", "register"]
