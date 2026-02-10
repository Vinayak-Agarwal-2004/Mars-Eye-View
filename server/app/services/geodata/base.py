from abc import ABC, abstractmethod
from typing import Any


class GeodataProvider(ABC):
    @abstractmethod
    def fetch(self, layer: str, params: dict | None = None, headers: dict | None = None) -> bytes | dict:
        pass

    @abstractmethod
    def health(self) -> bool:
        pass
