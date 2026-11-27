from abc import ABC, abstractmethod

from app.parsing.models import StructuredDocument


class Parser(ABC):
    name: str
    version: str

    @abstractmethod
    def parse(self, raw_bytes: bytes) -> StructuredDocument:
        ...
