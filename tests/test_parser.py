"""Tests for the hand-written tokenizer and parser."""

import pytest

from konfig.nodes import ExposeDecl, Literal, Ternary, Var, VarDecl
from konfig.errors import KonfigSyntaxError
from konfig.parser import parse, tokenize


def test_tokenize_kinds():
    tokens = tokenize("expose int port = 8080\nvar dev = true ? 1 : 2.5")
    kinds = [token.kind for token in tokens]
    assert kinds == [
        "NAME",
        "NAME",
        "NAME",
        "EQUALS",
        "INT",
        "NAME",
        "NAME",
        "EQUALS",
        "NAME",
        "QUESTION",
        "INT",
        "COLON",
        "FLOAT",
        "EOF",
    ]


def test_tokenize_positions_are_one_based():
    tokens = tokenize("var dev = 1")
    assert tokens[0].position.line == 1
    assert tokens[0].position.column == 1


def test_parse_expose_declaration():
    (decl,) = parse("expose int port = 8080")
    assert isinstance(decl, ExposeDecl)
    assert decl.name == "port"
    assert decl.type == "int"
    assert isinstance(decl.value, Literal)
    assert decl.value.value == 8080
    assert decl.value.kind == "int"
    assert decl.position.line == 1


def test_parse_var_declaration():
    (decl,) = parse("var dev = true")
    assert isinstance(decl, VarDecl)
    assert decl.name == "dev"
    assert isinstance(decl.value, Literal)
    assert decl.value.value is True
    assert decl.value.kind == "bool"


def test_parse_document_order_and_kinds():
    document = parse(
        """
        var dev = true

        expose int port = 8080
        expose string secret = "abc"
        expose bool debug = false
        expose float ratio = 1.5
        """
    )
    assert [type(decl).__name__ for decl in document] == [
        "VarDecl",
        "ExposeDecl",
        "ExposeDecl",
        "ExposeDecl",
        "ExposeDecl",
    ]
    kinds = [decl.value.kind for decl in document]  # type: ignore[union-attr]
    assert kinds == ["bool", "int", "string", "bool", "float"]


def test_float_precedes_int_in_lexer():
    (decl,) = parse("expose float ratio = 1.5")
    assert isinstance(decl, ExposeDecl)
    assert isinstance(decl.value, Literal)
    assert decl.value.value == 1.5
    assert decl.value.kind == "float"


def test_string_escapes():
    (decl,) = parse(r'expose string text = "a\nb\"q\\\u00e9"')
    assert isinstance(decl.value, Literal)
    assert decl.value.value == 'a\nb"q\\é'


def test_ternary_binds_branches_lazily_left_to_right():
    (decl,) = parse('expose string url = $dev ? "a" : "b"')
    assert isinstance(decl.value, Ternary)
    assert isinstance(decl.value.condition, Var)
    assert decl.value.condition.name == "dev"
    assert decl.value.then == Literal(value="a", kind="string", position=decl.value.then.position)
    assert decl.value.otherwise == Literal(value="b", kind="string", position=decl.value.otherwise.position)


def test_nested_ternary_is_right_associative():
    (decl,) = parse("var pick = false ? true ? 1 : 2 : 3")
    assert isinstance(decl.value, Ternary)
    assert decl.value.otherwise == Literal(value=3, kind="int", position=decl.value.otherwise.position)
    assert isinstance(decl.value.then, Ternary)


def test_empty_and_whitespace_documents():
    assert parse("") == []
    assert parse("   \n\t\r\n  ") == []


def test_unexpected_character_error():
    with pytest.raises(KonfigSyntaxError) as error:
        parse("var dev = @")
    assert "unexpected character '@'" in str(error.value)
    assert error.value.position.line == 1
    assert error.value.position.column == 11


def test_unterminated_string_error():
    with pytest.raises(KonfigSyntaxError) as error:
        parse('expose string s = "abc')
    assert "unterminated string literal" in str(error.value)
    assert error.value.position.line == 1


def test_invalid_escape_error():
    with pytest.raises(KonfigSyntaxError) as error:
        parse(r'expose string s = "bad\qescape"')
    assert "invalid escape sequence '\\q'" in str(error.value)


def test_unknown_type_error():
    with pytest.raises(KonfigSyntaxError) as error:
        parse("expose integer port = 8080")
    assert "unknown type 'integer'" in str(error.value)
    assert "int, float, string, bool" in str(error.value)


def test_missing_equals_error():
    with pytest.raises(KonfigSyntaxError) as error:
        parse("var dev 1\n")
    assert "expected '=', got '1'" in str(error.value)
    assert error.value.position.line == 1


def test_missing_value_error_position():
    with pytest.raises(KonfigSyntaxError) as error:
        parse("var dev =\nvar other = 1")
    assert error.value.position.line == 2
    assert error.value.position.column == 1


def test_declaration_keyword_missing():
    with pytest.raises(KonfigSyntaxError) as error:
        parse("port = 8080")
    assert "expected a declaration" in str(error.value)


def test_missing_colon_in_ternary():
    with pytest.raises(KonfigSyntaxError) as error:
        parse("var x = true ? 1 2")
    assert "expected ':'" in str(error.value)


def test_trailing_garbage_after_value():
    with pytest.raises(KonfigSyntaxError) as error:
        parse("var dev = true false")
    assert "expected a declaration" in str(error.value)
