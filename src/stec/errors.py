"""Custom exceptions raised by stec."""

from __future__ import annotations

from typing import Optional

from .nodes import Position


def _format_location(position: Optional[Position]) -> str:
    if position is None:
        return ""
    return f" at line {position.line}, column {position.column}"


class StecError(Exception):
    """Base class for every error raised by stec."""

    def __init__(self, message: str, position: Optional[Position] = None) -> None:
        super().__init__(f"{message}{_format_location(position)}")
        self.message = message
        self.position = position


class StecSyntaxError(StecError):
    """Raised when the source text cannot be tokenized or parsed."""


class StecTypeError(StecError):
    """Raised when a value does not match the type declared on ``expose``."""


class StecNameError(StecError):
    """Raised for undefined variable references or duplicate declarations."""


class StecLoadError(StecError):
    """Raised when the configuration file cannot be read."""


class StecAlreadyLoadedError(StecError):
    """Raised when ``Stec.load`` is called twice without ``force=True``."""
