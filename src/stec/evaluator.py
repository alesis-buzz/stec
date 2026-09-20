"""Evaluation of parsed stec documents into concrete values."""

from __future__ import annotations

import os

from .nodes import (
    Document,
    ExposeDecl,
    ExportEnvDecl,
    Expr,
    ImportEnvDecl,
    Interp,
    Literal,
    Position,
    Ternary,
    Var,
    VarDecl,
)
from .errors import StecError, StecNameError, StecTypeError


def _infer_type(value: object) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "string"
    raise StecError(f"internal error: unsupported value type {type(value).__name__}")


def _format_value(value: object) -> str:
    """Render a value for string interpolation."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _lookup(name: str, position: Position, environment: dict[str, object]) -> object:
    if name not in environment:
        raise StecNameError(
            f"undefined name {name!r}; it must be declared before it is used",
            position,
        )
    return environment[name]


def _eval_expr(expr: Expr, environment: dict[str, object]) -> object:
    if isinstance(expr, Literal):
        return expr.value
    if isinstance(expr, Var):
        return _lookup(expr.name, expr.position, environment)
    if isinstance(expr, Interp):
        return "".join(
            piece
            if isinstance(piece, str)
            else _format_value(_eval_expr(piece, environment))
            for piece in expr.parts
        )
    if isinstance(expr, Ternary):
        condition = _eval_expr(expr.condition, environment)
        if _infer_type(condition) != "bool":
            raise StecTypeError(
                f"ternary condition must be a bool, got "
                f"{_infer_type(condition)} {condition!r}",
                expr.position,
            )
        if condition:
            return _eval_expr(expr.then, environment)
        return _eval_expr(expr.otherwise, environment)
    raise StecError(
        f"internal error: unsupported expression node {type(expr).__name__}"
    )


def _coerce_env_value(
    name: str,
    raw: str,
    type_name: str,
    position: Position,
) -> object:
    """Coerce the raw string of an environment variable to a declared type."""
    if type_name == "string":
        return raw
    if type_name == "int":
        try:
            return int(raw)
        except ValueError:
            pass
    elif type_name == "float":
        try:
            return float(raw)
        except ValueError:
            pass
    elif type_name == "bool":
        lowered = raw.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
    raise StecTypeError(
        f"environment variable '{name}' has value {raw!r}, "
        f"which is not a valid '{type_name}'",
        position,
    )


def _check_duplicate(
    name: str,
    position: Position,
    environment: dict[str, object],
) -> None:
    if name in environment:
        raise StecNameError(f"duplicate declaration of {name!r}", position)


def evaluate(document: Document) -> dict[str, object]:
    """Evaluate a document in order and return the exposed values.

    ``var``, ``expose``, ``export env``, and ``import env`` declarations
    share one namespace: every declared name becomes available to ``$name``
    and ``${name}`` references made afterwards. ``export env`` statements
    also write to ``os.environ``. Only exposed and imported values are
    returned.
    """
    environment: dict[str, object] = {}
    exposed: dict[str, object] = {}
    for declaration in document:
        if isinstance(declaration, VarDecl):
            _check_duplicate(declaration.name, declaration.position, environment)
            environment[declaration.name] = _eval_expr(
                declaration.value, environment
            )
        elif isinstance(declaration, ExposeDecl):
            _check_duplicate(declaration.name, declaration.position, environment)
            value = _eval_expr(declaration.value, environment)
            actual_type = _infer_type(value)
            if actual_type != declaration.type:
                raise StecTypeError(
                    f"cannot expose {actual_type} value {value!r} "
                    f"as '{declaration.type}' for '{declaration.name}'",
                    declaration.position,
                )
            environment[declaration.name] = value
            exposed[declaration.name] = value
        elif isinstance(declaration, ExportEnvDecl):
            _check_duplicate(declaration.name, declaration.position, environment)
            value = _eval_expr(declaration.value, environment)
            os.environ[declaration.name] = _format_value(value)
            environment[declaration.name] = value
        elif isinstance(declaration, ImportEnvDecl):
            _check_duplicate(declaration.name, declaration.position, environment)
            raw = os.environ.get(declaration.name)
            if raw is None:
                if declaration.default is None:
                    raise StecNameError(
                        f"environment variable '{declaration.name}' is not set "
                        "and no default was provided",
                        declaration.position,
                    )
                value = _eval_expr(declaration.default, environment)
                actual_type = _infer_type(value)
                if actual_type != declaration.type:
                    raise StecTypeError(
                        f"invalid default for '{declaration.name}': expected "
                        f"'{declaration.type}', got {actual_type} {value!r}",
                        declaration.position,
                    )
            else:
                value = _coerce_env_value(
                    declaration.name,
                    raw,
                    declaration.type,
                    declaration.position,
                )
            environment[declaration.name] = value
            exposed[declaration.name] = value
        else:
            raise StecError(
                f"internal error: unsupported declaration node "
                f"{type(declaration).__name__}"
            )
    return exposed
