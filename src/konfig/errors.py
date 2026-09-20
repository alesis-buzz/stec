"""Custom exceptions raised by konfig."""

from __future__ import annotations

from typing import Optional

from .nodes import Position


def _format_location(position: Optional[Position]) -> str:
    if position is None:
        return ""
    return f" at line {position.line}, column {position.column}"


class KonfigError(Exception):
    """Base class for every error raised by konfig."""

    def __init__(self, message: str, position: Optional[Position] = None) -> None:
        super().__init__(f"{message}{_format_location(position)}")
        self.message = message
        self.position = position


class KonfigSyntaxError(KonfigError):
    """Raised when the source text cannot be tokenized or parsed."""


class KonfigTypeError(KonfigError):
    """Raised when a value does not match the type declared on ``expose``."""


class KonfigNameError(KonfigError):
    """Raised for undefined variable references or duplicate declarations."""


class KonfigLoadError(KonfigError):
    """Raised when the configuration file cannot be read."""


class KonfigAlreadyLoadedError(KonfigError):
    """Raised when ``Konfig.load`` is called twice without ``force=True``."""
