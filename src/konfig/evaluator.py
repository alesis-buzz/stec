"""Evaluation of parsed konfig documents into concrete values."""

from __future__ import annotations

from .nodes import (
    Document,
    ExposeDecl,
    Expr,
    Interp,
    Literal,
    Position,
    Ternary,
    Var,
    VarDecl,
)
from .errors import KonfigError, KonfigNameError, KonfigTypeError


def _infer_type(value: object) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "string"
    raise KonfigError(f"internal error: unsupported value type {type(value).__name__}")


def _format_value(value: object) -> str:
    """Render a value for string interpolation."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _lookup(name: str, position: Position, environment: dict[str, object]) -> object:
    if name not in environment:
        raise KonfigNameError(
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
            raise KonfigTypeError(
                f"ternary condition must be a bool, got "
                f"{_infer_type(condition)} {condition!r}",
                expr.position,
            )
        if condition:
            return _eval_expr(expr.then, environment)
        return _eval_expr(expr.otherwise, environment)
    raise KonfigError(
        f"internal error: unsupported expression node {type(expr).__name__}"
    )


def _check_duplicate(
    name: str,
    position: Position,
    environment: dict[str, object],
) -> None:
    if name in environment:
        raise KonfigNameError(f"duplicate declaration of {name!r}", position)


def evaluate(document: Document) -> dict[str, object]:
    """Evaluate a document in order and return the exposed values.

    ``var`` and ``expose`` declarations share one namespace: every declared
    name becomes available to ``$name`` and ``${name}`` references made
    afterwards. Only the exposed values are returned.
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
                raise KonfigTypeError(
                    f"cannot expose {actual_type} value {value!r} "
                    f"as '{declaration.type}' for '{declaration.name}'",
                    declaration.position,
                )
            environment[declaration.name] = value
            exposed[declaration.name] = value
        else:
            raise KonfigError(
                f"internal error: unsupported declaration node "
                f"{type(declaration).__name__}"
            )
    return exposed
