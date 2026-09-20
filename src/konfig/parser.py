"""Tokenizer and recursive-descent parser for the konfig language."""

from __future__ import annotations

import re
from dataclasses import dataclass

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
from .errors import KonfigSyntaxError

_TOKEN_PATTERN = re.compile(
    r"""
      (?P<WS>\s+)
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
}


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
                    raise KonfigSyntaxError(
                        "unterminated string literal",
                        _position_at(source, index),
                    )
            raise KonfigSyntaxError(
                f"unexpected character {char!r}",
                _position_at(source, index),
            )
        if match.lastgroup != "WS":
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


def _unescape_string(raw: str, position: Position) -> str:
    """Decode the escape sequences of a quoted string literal."""
    body = raw[1:-1]
    pieces: list[str] = []
    index = 0
    while index < len(body):
        char = body[index]
        if char != "\\":
            pieces.append(char)
            index += 1
            continue
        escape = body[index + 1] if index + 1 < len(body) else None
        if escape is None:
            raise KonfigSyntaxError(
                "unterminated escape sequence in string literal", position
            )
        simple = _SIMPLE_ESCAPES.get(escape)
        if simple is not None:
            pieces.append(simple)
            index += 2
            continue
        if escape == "u":
            digits = body[index + 2 : index + 6]
            if len(digits) != 4 or not set(digits) <= _HEX_DIGITS:
                raise KonfigSyntaxError(
                    "invalid \\uXXXX escape sequence in string literal", position
                )
            pieces.append(chr(int(digits, 16)))
            index += 6
            continue
        raise KonfigSyntaxError(
            f"invalid escape sequence '\\{escape}' in string literal", position
        )
    return "".join(pieces)


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
        if token.kind == "NAME" and token.value == "expose":
            return self._parse_expose()
        if token.kind == "NAME" and token.value == "var":
            return self._parse_var()
        raise KonfigSyntaxError(
            f"expected a declaration ('var' or 'expose'), got {_describe(token)}",
            token.position,
        )

    def _parse_expose(self) -> ExposeDecl:
        keyword = self._advance()
        type_token = self._expect("NAME", "a type name")
        if type_token.value not in _TYPE_NAMES:
            raise KonfigSyntaxError(
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
            return Literal(
                value=_unescape_string(token.value, token.position),
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
        raise KonfigSyntaxError(
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
            raise KonfigSyntaxError(
                f"expected {description}, got {_describe(token)}",
                token.position,
            )
        return self._advance()


def parse(source: str) -> Document:
    """Parse konfig source text into a document (a list of declarations)."""
    return _Parser(tokenize(source)).parse_document()
