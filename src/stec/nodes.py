"""Abstract syntax tree nodes for stec documents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union


@dataclass(frozen=True)
class Position:
    """A one-based (line, column) location in the source text."""

    line: int
    column: int

    def __str__(self) -> str:
        return f"{self.line}:{self.column}"


@dataclass(frozen=True)
class Literal:
    """A literal value: int, float, string, or bool."""

    value: object
    kind: str
    position: Position


@dataclass(frozen=True)
class Var:
    """A reference to a previously declared ``var``."""

    name: str
    position: Position


@dataclass(frozen=True)
class Ternary:
    """A conditional expression: ``condition ? then : otherwise``."""

    condition: Expr
    then: Expr
    otherwise: Expr
    position: Position


@dataclass(frozen=True)
class Interp:
    """A string containing ``${name}`` interpolations.

    ``parts`` alternates literal string chunks and variable references.
    """

    parts: tuple[Union[str, Var], ...]
    position: Position


Expr = Union[Literal, Var, Ternary, Interp]


@dataclass(frozen=True)
class VarDecl:
    """An internal variable declaration: ``var NAME = value``."""

    name: str
    value: Expr
    position: Position


@dataclass(frozen=True)
class ExposeDecl:
    """A public, typed configuration value: ``expose TYPE NAME = value``."""

    name: str
    type: str
    value: Expr
    position: Position


@dataclass(frozen=True)
class ExportEnvDecl:
    """An environment export: ``export env NAME = value``."""

    name: str
    value: Expr
    position: Position


@dataclass(frozen=True)
class ImportEnvDecl:
    """An environment import: ``import env TYPE NAME [= default]``."""

    name: str
    type: str
    default: Optional[Expr]
    position: Position


Document = list[Union[VarDecl, ExposeDecl, ExportEnvDecl, ImportEnvDecl]]
