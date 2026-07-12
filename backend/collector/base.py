from abc import ABC, abstractmethod


class BaseCollector(ABC):
    """Base class for all data collectors."""

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    async def fetch(self) -> list[dict]:
        """Fetch raw data from source."""
        pass

    @abstractmethod
    async def transform(self, raw: dict) -> dict:
        """Transform raw data to standardized item."""
        pass

    @abstractmethod
    async def validate(self, item: dict) -> bool:
        """Validate transformed item."""
        pass
