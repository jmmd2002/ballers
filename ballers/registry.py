"""Registry of selectable fighters. Every module in the roster packages
(ballers/balls/, ballers/politics/; except those starting with "_") is imported
automatically, so adding a fighter is just adding a file with an @register class."""
from __future__ import annotations

import importlib
import pkgutil

from .fighter import Fighter

PACKAGES = ("balls", "politics", "countries")   # one per roster, kept apart to stay tidy

_REGISTRY: dict[str, type[Fighter]] = {}
_loaded = False


def register(cls: type[Fighter]) -> type[Fighter]:
    if cls.key in _REGISTRY:
        raise ValueError(f"Duplicate fighter key: {cls.key!r}")
    _REGISTRY[cls.key] = cls
    return cls


def _load_all():
    global _loaded
    if _loaded:
        return
    for package in PACKAGES:
        pkg = importlib.import_module(f"{__package__}.{package}")
        for mod in pkgutil.iter_modules(pkg.__path__):
            if not mod.name.startswith("_"):
                importlib.import_module(f"{pkg.__name__}.{mod.name}")
    _loaded = True


def all_fighters() -> list[type[Fighter]]:
    _load_all()
    return list(_REGISTRY.values())


def categories() -> list[str]:
    """Roster names in registration order, e.g. ["anime", "politics"]."""
    return list(dict.fromkeys(cls.category for cls in all_fighters()))


def get(key: str) -> type[Fighter]:
    _load_all()
    try:
        return _REGISTRY[key]
    except KeyError:
        raise KeyError(f"Unknown fighter {key!r}. Available: {', '.join(_REGISTRY)}") from None
