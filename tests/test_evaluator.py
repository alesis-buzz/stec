"""Tests for document evaluation and type checking."""

import pytest

from konfig.errors import KonfigNameError, KonfigTypeError
from konfig.evaluator import evaluate
from konfig.parser import parse

SAMPLE = """
var dev = true

expose int port = 8080
expose string secret = "abc"
expose string url = $dev ? "127.0.0.1" : "0.0.0.0"
"""


def test_evaluate_sample_document():
    values = evaluate(parse(SAMPLE))
    assert values == {
        "port": 8080,
        "secret": "abc",
        "url": "127.0.0.1",
    }


def test_vars_are_not_exposed():
    values = evaluate(parse(SAMPLE))
    assert "dev" not in values


def test_all_types_round_trip():
    values = evaluate(
        parse(
            """
            expose int a = 1
            expose float b = 2.5
            expose string c = "x"
            expose bool d = false
            """
        )
    )
    assert values == {"a": 1, "b": 2.5, "c": "x", "d": False}
    assert type(values["a"]) is int
    assert type(values["b"]) is float
    assert type(values["c"]) is str
    assert type(values["d"]) is bool


def test_type_mismatch_int_gets_string():
    with pytest.raises(KonfigTypeError) as error:
        evaluate(parse('expose int port = "abc"'))
    assert "cannot expose string value 'abc' as 'int' for 'port'" in str(error.value)


def test_bool_is_not_a_valid_int():
    with pytest.raises(KonfigTypeError) as error:
        evaluate(parse("expose int port = true"))
    assert "cannot expose bool value True as 'int'" in str(error.value)


def test_int_is_not_a_valid_float():
    with pytest.raises(KonfigTypeError) as error:
        evaluate(parse("expose float ratio = 1"))
    assert "cannot expose int value 1 as 'float'" in str(error.value)


def test_type_error_reports_position():
    with pytest.raises(KonfigTypeError) as error:
        evaluate(parse('var ok = true\nexpose int port = "abc"'))
    assert error.value.position.line == 2


def test_undefined_variable():
    with pytest.raises(KonfigNameError) as error:
        evaluate(parse('expose string url = $missing ? "a" : "b"'))
    assert "undefined name 'missing'" in str(error.value)


def test_variable_must_be_declared_before_use():
    with pytest.raises(KonfigNameError) as error:
        evaluate(parse(
            """
            expose string url = $dev ? "a" : "b"
            var dev = true
            """
        ))
    assert "undefined name 'dev'" in str(error.value)


def test_duplicate_var_declaration():
    with pytest.raises(KonfigNameError) as error:
        evaluate(parse("var dev = true\nvar dev = false"))
    assert "duplicate declaration of 'dev'" in str(error.value)


def test_var_and_expose_share_a_namespace():
    with pytest.raises(KonfigNameError) as error:
        evaluate(parse("var port = 1\nexpose int port = 8080"))
    assert "duplicate declaration of 'port'" in str(error.value)


def test_ternary_condition_must_be_bool():
    with pytest.raises(KonfigTypeError) as error:
        evaluate(parse('expose string url = 1 ? "a" : "b"'))
    assert "ternary condition must be a bool, got int 1" in str(error.value)


def test_ternary_uses_then_branch():
    values = evaluate(parse('var dev = false\nexpose string url = $dev ? "a" : "b"'))
    assert values == {"url": "b"}


def test_nested_ternary_evaluation():
    values = evaluate(
        parse(
            """
            var debug = false
            var warn = true
            expose string mode = $debug ? "debug" : $warn ? "warn" : "prod"
            """
        )
    )
    assert values == {"mode": "warn"}


def test_late_take_branch_still_checked_by_expose_type():
    with pytest.raises(KonfigTypeError):
        evaluate(parse('var dev = false\nexpose string url = $dev ? "a" : 2'))

def test_interpolation_joins_chunks_and_references():
    values = evaluate(
        parse(
            """
            var host = "localhost"
            expose int port = 8080
            expose string url = "http://${host}:${port}/"
            """
        )
    )
    assert values["url"] == "http://localhost:8080/"


def test_interpolation_formats_bools_like_the_language():
    values = evaluate(
        parse(
            """
            var debug = true
            var quiet = false
            expose string mode = "debug=${debug} quiet=${quiet}"
            """
        )
    )
    assert values["mode"] == "debug=true quiet=false"


def test_interpolation_formats_numbers():
    values = evaluate(
        parse(
            """
            expose float ratio = 1.5
            expose string label = "ratio=${ratio}"
            """
        )
    )
    assert values["label"] == "ratio=1.5"


def test_interpolation_of_an_interpolated_var():
    values = evaluate(
        parse(
            """
            var a = "x"
            var b = "${a}y"
            expose string c = "z${b}z"
            """
        )
    )
    assert values["c"] == "zxyz"


def test_interpolation_can_reference_earlier_exposes():
    values = evaluate(
        parse(
            """
            expose int port = 8080
            expose string url = "http://localhost:${port}"
            """
        )
    )
    assert values["url"] == "http://localhost:8080"


def test_interpolation_cannot_reference_later_declarations():
    with pytest.raises(KonfigNameError) as error:
        evaluate(parse(
            """
            expose string url = "http://localhost:${port}"
            expose int port = 8080
            """
        ))
    assert "undefined name 'port'" in str(error.value)


def test_undefined_name_inside_interpolation_reports_string_position():
    with pytest.raises(KonfigNameError) as error:
        evaluate(parse('expose string url = "http://${missing}/"'))
    assert error.value.position.column == 29


def test_comments_and_interpolation_together():
    values = evaluate(
        parse(
            """
            # runtime switches
            var dev = true  # flip for prod

            # service endpoints
            expose string base = $dev ? "http://127.0.0.1" : "http://example.com"
            expose int port = 8080
            expose string api = "${base}:${port}/api"
            """
        )
    )
    assert values == {
        "base": "http://127.0.0.1",
        "port": 8080,
        "api": "http://127.0.0.1:8080/api",
    }
