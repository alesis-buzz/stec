"""Tokenizer and recursive-descent parser for the stec language."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

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
from .errors import StecSyntaxError

_TOKEN_PATTERN = re.compile(
    r"""
      (?P<WS>\s+)
    | (?P<COMMENT>\#[^\n]*)
    | (?P<FLOAT>\d+\.\d+)
    | (?P<INT>\d+)
    | (?P<STRING>"(?:\\.|[^"\\\n])*")
    | (?P<VARIABLE>\$[A-Za-z_]\w*)
    | (?P<NAME>[A-Za-z_]\w*)
    | (?P<EQUALS>=)
    | (?P<QUESTION>\?)
    | (?P<COLON>:)
    """,
    re.VERBOSE,
)

_TYPE_NAMES = ("int", "float", "string", "bool")
_BOOL_LITERALS = frozenset({"true", "false"})
_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")

_SIMPLE_ESCAPES = {
    '"': '"',
    "\\": "\\",
    "n": "\n",
    "t": "\t",
    "r": "\r",
    "0": "\0",
    "b": "\b",
    "f": "\f",
    "$": "$",
}

_INTERP_NAME = re.compile(r"[A-Za-z_]\w*")


@dataclass(frozen=True)
class Token:
    """A lexical token with its source position."""

    kind: str
    value: str
    position: Position


def _position_at(source: str, index: int) -> Position:
    line = source.count("\n", 0, index) + 1
    last_newline = source.rfind("\n", 0, index)
    column = index - last_newline
    return Position(line=line, column=column)


def tokenize(source: str) -> list[Token]:
    """Split *source* into a token list, skipping whitespace."""
    tokens: list[Token] = []
    index = 0
    length = len(source)
    while index < length:
        match = _TOKEN_PATTERN.match(source, index)
        if match is None:
            char = source[index]
            if char == '"':
                closing = source.find('"', index + 1)
                if closing == -1 or "\n" in source[index + 1 : closing]:
                    raise StecSyntaxError(
                        "unterminated string literal",
                        _position_at(source, index),
                    )
            raise StecSyntaxError(
                f"unexpected character {char!r}",
                _position_at(source, index),
            )
        if match.lastgroup not in ("WS", "COMMENT"):
            tokens.append(
                Token(
                    kind=match.lastgroup,
                    value=match.group(0),
                    position=_position_at(source, match.start()),
                )
            )
        index = match.end()
    tokens.append(Token(kind="EOF", value="", position=_position_at(source, length)))
    return tokens


def _describe(token: Token) -> str:
    if token.kind == "EOF":
        return "end of input"
    return repr(token.value)


def _decode_escape(body: str, index: int, position: Position) -> tuple[str, int]:
    """Decode the escape sequence starting at ``body[index]`` (the backslash).

    Returns the decoded text and the index just after the escape.
    """
    escape = body[index + 1] if index + 1 < len(body) else None
    if escape is None:
        raise StecSyntaxError(
            "unterminated escape sequence in string literal", position
        )
    simple = _SIMPLE_ESCAPES.get(escape)
    if simple is not None:
        return simple, index + 2
    if escape == "u":
        digits = body[index + 2 : index + 6]
        if len(digits) != 4 or not set(digits) <= _HEX_DIGITS:
            raise StecSyntaxError(
                "invalid \\uXXXX escape sequence in string literal", position
            )
        return chr(int(digits, 16)), index + 6
    raise StecSyntaxError(
        f"invalid escape sequence '\\{escape}' in string literal", position
    )


def _within(token_position: Position, body_index: int) -> Position:
    """Map an index inside a string token body to a source position."""
    return Position(
        line=token_position.line,
        column=token_position.column + 1 + body_index,
    )


def _parse_string_literal(raw: str, position: Position) -> "str | Interp":
    """Decode a quoted string literal, resolving ``${name}`` interpolations.

    Returns a plain string when there is nothing to interpolate, and an
    ``Interp`` node otherwise.
    """
    body = raw[1:-1]
    parts: list["str | Var"] = []
    text: list[str] = []
    index = 0
    length = len(body)
    interpolating = False
    while index < length:
        char = body[index]
        if char == "\\":
            decoded, index = _decode_escape(
                body, index, _within(position, index)
            )
            text.append(decoded)
            continue
        if char == "$" and index + 1 < length and body[index + 1] == "{":
            name_match = _INTERP_NAME.match(body, index + 2)
            if name_match is None:
                raise StecSyntaxError(
                    "missing variable name in '${...}' interpolation",
                    _within(position, index),
                )
            name = name_match.group(0)
            closing = name_match.end()
            if closing >= length or body[closing] != "}":
                raise StecSyntaxError(
                    f"missing '}}' in '${{{name}}}' interpolation",
                    _within(position, index),
                )
            interpolating = True
            if text:
                parts.append("".join(text))
                text = []
            parts.append(Var(name=name, position=_within(position, index)))
            index = closing + 1
            continue
        text.append(char)
        index += 1
    if not interpolating:
        return "".join(text)
    if text:
        parts.append("".join(text))
    return Interp(parts=tuple(parts), position=position)


class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self._tokens = tokens
        self._index = 0

    def parse_document(self) -> Document:
        declarations: Document = []
        while not self._at_end():
            declarations.append(self._parse_statement())
        return declarations

    def _parse_statement(self):
        token = self._peek()
        if token.kind == "NAME":
            if token.value == "expose":
                return self._parse_expose()
            if token.value == "var":
                return self._parse_var()
            if token.value == "export":
                return self._parse_export_env()
            if token.value == "import":
                return self._parse_import_env()
        raise StecSyntaxError(
            "expected a declaration ('var', 'expose', 'export', or 'import'), got "
            + _describe(token),
            token.position,
        )

    def _parse_expose(self) -> ExposeDecl:
        keyword = self._advance()
        type_token = self._expect("NAME", "a type name")
        if type_token.value not in _TYPE_NAMES:
            raise StecSyntaxError(
                f"unknown type {type_token.value!r}, expected one of: "
                + ", ".join(_TYPE_NAMES),
                type_token.position,
            )
        name_token = self._expect("NAME", "a value name")
        self._expect("EQUALS", "'='")
        value = self._parse_value()
        return ExposeDecl(
            name=name_token.value,
            type=type_token.value,
            value=value,
            position=keyword.position,
        )

    def _parse_var(self) -> VarDecl:
        keyword = self._advance()
        name_token = self._expect("NAME", "a variable name")
        self._expect("EQUALS", "'='")
        value = self._parse_value()
        return VarDecl(name=name_token.value, value=value, position=keyword.position)

    def _parse_export_env(self) -> ExportEnvDecl:
        keyword = self._advance()
        self._expect_env_keyword(keyword.value)
        name_token = self._expect("NAME", "an environment variable name")
        self._expect("EQUALS", "'='")
        value = self._parse_value()
        return ExportEnvDecl(
            name=name_token.value, value=value, position=keyword.position
        )

    def _parse_import_env(self) -> ImportEnvDecl:
        keyword = self._advance()
        self._expect_env_keyword(keyword.value)
        type_token = self._expect("NAME", "a type name")
        if type_token.value not in _TYPE_NAMES:
            raise StecSyntaxError(
                f"unknown type {type_token.value!r}, expected one of: "
                + ", ".join(_TYPE_NAMES),
                type_token.position,
            )
        name_token = self._expect("NAME", "an environment variable name")
        default: Optional[Expr] = None
        if self._peek().kind == "EQUALS":
            self._advance()
            default = self._parse_value()
        return ImportEnvDecl(
            name=name_token.value,
            type=type_token.value,
            default=default,
            position=keyword.position,
        )

    def _expect_env_keyword(self, statement: str) -> None:
        token = self._peek()
        if token.kind != "NAME" or token.value != "env":
            raise StecSyntaxError(
                f"expected 'env' after '{statement}', got {_describe(token)}",
                token.position,
            )
        self._advance()

    def _parse_value(self) -> Expr:
        atom = self._parse_atom()
        if self._peek().kind != "QUESTION":
            return atom
        question = self._advance()
        then_value = self._parse_value()
        self._expect("COLON", "':'")
        otherwise = self._parse_value()
        return Ternary(
            condition=atom,
            then=then_value,
            otherwise=otherwise,
            position=question.position,
        )

    def _parse_atom(self) -> Expr:
        token = self._peek()
        if token.kind == "INT":
            self._advance()
            return Literal(value=int(token.value), kind="int", position=token.position)
        if token.kind == "FLOAT":
            self._advance()
            return Literal(
                value=float(token.value), kind="float", position=token.position
            )
        if token.kind == "STRING":
            self._advance()
            string_value = _parse_string_literal(token.value, token.position)
            if isinstance(string_value, Interp):
                return string_value
            return Literal(
                value=string_value,
                kind="string",
                position=token.position,
            )
        if token.kind == "VARIABLE":
            self._advance()
            return Var(name=token.value[1:], position=token.position)
        if token.kind == "NAME" and token.value in _BOOL_LITERALS:
            self._advance()
            return Literal(
                value=token.value == "true", kind="bool", position=token.position
            )
        raise StecSyntaxError(
            "expected a value (number, string, bool, or $variable), got "
            + _describe(token),
            token.position,
        )

    def _at_end(self) -> bool:
        return self._peek().kind == "EOF"

    def _peek(self) -> Token:
        return self._tokens[self._index]

    def _advance(self) -> Token:
        token = self._tokens[self._index]
        self._index += 1
        return token

    def _expect(self, kind: str, description: str) -> Token:
        token = self._peek()
        if token.kind != kind:
            raise StecSyntaxError(
                f"expected {description}, got {_describe(token)}",
                token.position,
            )
        return self._advance()


def parse(source: str) -> Document:
    """Parse stec source text into a document (a list of declarations)."""
    return _Parser(tokenize(source)).parse_document()
