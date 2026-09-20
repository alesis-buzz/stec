"""Tests for document evaluation and type checking."""

import pytest

from stec.errors import StecNameError, StecTypeError
from stec.evaluator import evaluate
from stec.parser import parse

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
    with pytest.raises(StecTypeError) as error:
        evaluate(parse('expose int port = "abc"'))
    assert "cannot expose string value 'abc' as 'int' for 'port'" in str(error.value)


def test_bool_is_not_a_valid_int():
    with pytest.raises(StecTypeError) as error:
        evaluate(parse("expose int port = true"))
    assert "cannot expose bool value True as 'int'" in str(error.value)


def test_int_is_not_a_valid_float():
    with pytest.raises(StecTypeError) as error:
        evaluate(parse("expose float ratio = 1"))
    assert "cannot expose int value 1 as 'float'" in str(error.value)


def test_type_error_reports_position():
    with pytest.raises(StecTypeError) as error:
        evaluate(parse('var ok = true\nexpose int port = "abc"'))
    assert error.value.position.line == 2


def test_undefined_variable():
    with pytest.raises(StecNameError) as error:
        evaluate(parse('expose string url = $missing ? "a" : "b"'))
    assert "undefined name 'missing'" in str(error.value)


def test_variable_must_be_declared_before_use():
    with pytest.raises(StecNameError) as error:
        evaluate(parse(
            """
            expose string url = $dev ? "a" : "b"
            var dev = true
            """
        ))
    assert "undefined name 'dev'" in str(error.value)


def test_duplicate_var_declaration():
    with pytest.raises(StecNameError) as error:
        evaluate(parse("var dev = true\nvar dev = false"))
    assert "duplicate declaration of 'dev'" in str(error.value)


def test_var_and_expose_share_a_namespace():
    with pytest.raises(StecNameError) as error:
        evaluate(parse("var port = 1\nexpose int port = 8080"))
    assert "duplicate declaration of 'port'" in str(error.value)


def test_ternary_condition_must_be_bool():
    with pytest.raises(StecTypeError) as error:
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
    with pytest.raises(StecTypeError):
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
    with pytest.raises(StecNameError) as error:
        evaluate(parse(
            """
            expose string url = "http://localhost:${port}"
            expose int port = 8080
            """
        ))
    assert "undefined name 'port'" in str(error.value)


def test_undefined_name_inside_interpolation_reports_string_position():
    with pytest.raises(StecNameError) as error:
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

import os

import pytest


@pytest.fixture()
def guarded_env():
    """Snapshot os.environ and restore it after the test.

    ``export env`` writes to os.environ directly, so a snapshot is the only
    reliable way to undo its side effects.
    """
    snapshot = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(snapshot)


def test_export_env_writes_to_environment(guarded_env):
    values = evaluate(parse('export env STEC_TEST_FLAG = "hello"'))
    assert values == {}
    assert os.environ["STEC_TEST_FLAG"] == "hello"


def test_export_env_formats_bools_and_numbers(guarded_env):
    evaluate(parse("export env STEC_TEST_N = 5\nexport env STEC_TEST_B = true"))
    assert os.environ["STEC_TEST_N"] == "5"
    assert os.environ["STEC_TEST_B"] == "true"


def test_exported_names_are_usable_later(guarded_env):
    values = evaluate(
        parse(
            'export env STEC_TEST_BASE = "http://x"\n'
            'expose string url = "${STEC_TEST_BASE}/api"'
        )
    )
    assert values == {"url": "http://x/api"}


def test_export_env_is_not_published(guarded_env):
    values = evaluate(parse("var n = 2\nexport env STEC_TEST_N = 5"))
    assert "STEC_TEST_N" not in values
    assert "n" not in values


def test_import_env_reads_existing_environment(guarded_env):
    os.environ["STEC_TEST_PORT"] = "9090"
    values = evaluate(parse("import env int STEC_TEST_PORT = 1"))
    assert values == {"STEC_TEST_PORT": 9090}


def test_import_env_uses_default_when_missing(guarded_env):
    os.environ.pop("STEC_TEST_MISSING", None)
    values = evaluate(parse('import env string STEC_TEST_MISSING = "fallback"'))
    assert values == {"STEC_TEST_MISSING": "fallback"}


def test_import_env_without_default_and_missing_raises(guarded_env):
    os.environ.pop("STEC_TEST_MISSING", None)
    with pytest.raises(StecNameError) as error:
        evaluate(parse("import env string STEC_TEST_MISSING"))
    assert "environment variable 'STEC_TEST_MISSING' is not set" in str(error.value)


def test_import_env_coercion_failure(guarded_env):
    os.environ["STEC_TEST_NOT_A_NUMBER"] = "abc"
    with pytest.raises(StecTypeError) as error:
        evaluate(parse("import env int STEC_TEST_NOT_A_NUMBER = 0"))
    assert "not a valid 'int'" in str(error.value)


def test_import_env_bool_coercion_is_case_insensitive(guarded_env):
    os.environ["STEC_TEST_B1"] = "true"
    os.environ["STEC_TEST_B2"] = "FALSE"
    values = evaluate(
        parse("import env bool STEC_TEST_B1\nimport env bool STEC_TEST_B2")
    )
    assert values == {"STEC_TEST_B1": True, "STEC_TEST_B2": False}


def test_import_env_invalid_bool_raises(guarded_env):
    os.environ["STEC_TEST_B3"] = "yes"
    with pytest.raises(StecTypeError) as error:
        evaluate(parse("import env bool STEC_TEST_B3"))
    assert "not a valid 'bool'" in str(error.value)


def test_import_env_default_type_must_match():
    with pytest.raises(StecTypeError) as error:
        evaluate(parse('import env int STEC_TEST_PORT = "abc"'))
    assert "invalid default for 'STEC_TEST_PORT'" in str(error.value)


def test_export_and_var_share_a_namespace():
    with pytest.raises(StecNameError) as error:
        evaluate(parse("var X = 1\nexport env X = 2"))
    assert "duplicate declaration of 'X'" in str(error.value)


def test_import_and_expose_share_a_namespace():
    with pytest.raises(StecNameError) as error:
        evaluate(parse('import env string X = "d"\nexpose string X = "e"'))
    assert "duplicate declaration of 'X'" in str(error.value)
