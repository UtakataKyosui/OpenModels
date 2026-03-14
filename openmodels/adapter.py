from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


class AdapterError(Exception):
    pass


@dataclass(frozen=True)
class GeneratedFile:
    path: str
    content: str


class BackendAdapter(ABC):
    key: str
    description: str
    default_filename: str

    @abstractmethod
    def generate_files(
        self,
        canonical_model: dict[str, Any],
        filename: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> list[GeneratedFile]:
        raise NotImplementedError
