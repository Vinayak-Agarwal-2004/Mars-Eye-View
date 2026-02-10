from typing import TYPE_CHECKING

from server.app.services.geodata.geoboundaries import GeoBoundariesProvider
from server.app.services.geodata.natural_earth import NaturalEarthProvider

if TYPE_CHECKING:
    from server.app.services.geodata.base import GeodataProvider

_registry: dict[str, "GeodataProvider"] = {}


def _ensure_defaults():
    if not _registry:
        _registry["geoboundaries"] = GeoBoundariesProvider()
        _registry["natural_earth"] = NaturalEarthProvider()


def register_provider(name: str, provider: "GeodataProvider"):
    _registry[name] = provider


def get_provider(name: str) -> "GeodataProvider":
    _ensure_defaults()
    p = _registry.get(name)
    if p is None:
        raise KeyError(f"Unknown provider: {name}")
    return p
