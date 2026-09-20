"""Evaluation of parsed konfig documents into concrete values."""

from __future__ import annotations

from .nodes import (
    Document,
    ExposeDecl,
    Expr,
    Literal,
    Position,
    Ternary,
    Var,
    VarDecl,
)
from .errors import KonfigError, KonfigNameError, KonfigTypeError

_TYPE_NAMES = ("int", "float", "string", "bool")


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


def _eval_expr(expr: Expr, variables: dict[str, object]) -> object:
    if isinstance(expr, Literal):
        return expr.value
    if isinstance(expr, Var):
        if expr.name not in variables:
            raise KonfigNameError(
                f"undefined variable {expr.name!r}; vars must be declared before use",
                expr.position,
            )
        return variables[expr.name]
    if isinstance(expr, Ternary):
        condition = _eval_expr(expr.condition, variables)
        if _infer_type(condition) != "bool":
            raise KonfigTypeError(
                f"ternary condition must be a bool, got "
                f"{_infer_type(condition)} {condition!r}",
                expr.position,
            )
        if condition:
            return _eval_expr(expr.then, variables)
        return _eval_expr(expr.otherwise, variables)
    raise KonfigError(
        f"internal error: unsupported expression node {type(expr).__name__}"
    )


def evaluate(document: Document) -> dict[str, object]:
    """Evaluate a document in order and return the exposed values.

    ``var`` declarations go into an internal environment used to resolve
    ``$name`` references and are not part of the returned mapping.
    """
    variables: dict[str, object] = {}
    exposed: dict[str, object] = {}
    for declaration in document:
        if isinstance(declaration, VarDecl):
            _check_duplicate(declaration.name, declaration.position, variables, exposed)
            variables[declaration.name] = _eval_expr(declaration.value, variables)
        elif isinstance(declaration, ExposeDecl):
            _check_duplicate(declaration.name, declaration.position, variables, exposed)
            value = _eval_expr(declaration.value, variables)
            actual_type = _infer_type(value)
            if actual_type != declaration.type:
                raise KonfigTypeError(
                    f"cannot expose {actual_type} value {value!r} "
                    f"as '{declaration.type}' for '{declaration.name}'",
                    declaration.position,
                )
            exposed[declaration.name] = value
        else:
            raise KonfigError(
                f"internal error: unsupported declaration node "
                f"{type(declaration).__name__}"
            )
    return exposed


def _check_duplicate(
    name: str,
    position: Position,
    variables: dict[str, object],
    exposed: dict[str, object],
) -> None:
    if name in variables or name in exposed:
        raise KonfigNameError(f"duplicate declaration of {name!r}", position)
