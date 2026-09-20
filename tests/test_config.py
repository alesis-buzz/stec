"""Tests for the Stec singleton."""

import pytest

from stec import (
    Stec,
    StecAlreadyLoadedError,
    StecLoadError,
    StecSyntaxError,
)

GOOD = """
var dev = true

expose int port = 8080
expose string url = $dev ? "127.0.0.1" : "0.0.0.0"
"""


@pytest.fixture()
def fresh_stec():
    Stec.reset()
    yield
    Stec.reset()


def write_config(tmp_path, text):
    path = tmp_path / "app.stec"
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_load_and_access_everywhere(tmp_path, fresh_stec):
    Stec.load(write_config(tmp_path, GOOD))

    assert Stec.is_loaded
    assert Stec.port == 8080
    assert Stec["url"] == "127.0.0.1"
    assert Stec.get("port") == 8080
    assert Stec.get("missing") is None
    assert Stec.get("missing", 5) == 5
    assert Stec.as_dict() == {"port": 8080, "url": "127.0.0.1"}
    assert "port" in Stec
    assert "dev" not in Stec


def test_vars_are_hidden_from_public_api(tmp_path, fresh_stec):
    Stec.load(write_config(tmp_path, GOOD))

    with pytest.raises(AttributeError):
        Stec.dev  # noqa: B018
    with pytest.raises(KeyError):
        Stec["dev"]
    assert "dev" not in Stec.as_dict()


def test_stec_is_a_true_singleton(fresh_stec):
    from stec.config import Stec as StecClass

    assert StecClass() is Stec
    assert StecClass() is StecClass()


def test_load_returns_the_singleton(tmp_path, fresh_stec):
    assert Stec.load(write_config(tmp_path, GOOD)) is Stec


def test_double_load_without_force_raises(tmp_path, fresh_stec):
    path = write_config(tmp_path, GOOD)
    Stec.load(path)

    with pytest.raises(StecAlreadyLoadedError) as error:
        Stec.load(path)
    assert "already loaded" in str(error.value)


def test_force_reload_picks_up_changes(tmp_path, fresh_stec):
    path = write_config(tmp_path, GOOD)
    Stec.load(path)

    write_config(tmp_path, "expose int port = 9090")
    Stec.load(path, force=True)

    assert Stec.port == 9090
    assert "url" not in Stec.as_dict()
    assert Stec.loaded_from == path


def test_load_missing_file(tmp_path, fresh_stec):
    with pytest.raises(StecLoadError):
        Stec.load(str(tmp_path / "missing.stec"))


def test_load_file_with_syntax_error(tmp_path, fresh_stec):
    with pytest.raises(StecSyntaxError):
        Stec.load(write_config(tmp_path, "var broken = @"))


def test_failed_load_does_not_mark_singleton_as_loaded(tmp_path, fresh_stec):
    with pytest.raises(StecSyntaxError):
        Stec.load(write_config(tmp_path, "var broken = @"))

    assert not Stec.is_loaded

    Stec.load(write_config(tmp_path, GOOD))
    assert Stec.port == 8080


def test_reset_clears_state(tmp_path, fresh_stec):
    Stec.load(write_config(tmp_path, GOOD))
    Stec.reset()

    assert not Stec.is_loaded
    with pytest.raises(AttributeError):
        Stec.port  # noqa: B018


def test_repr_does_not_leak_values(tmp_path, fresh_stec):
    Stec.load(write_config(tmp_path, 'expose string secret = "topsecret"'))

    rendered = repr(Stec)
    assert "topsecret" not in rendered
    assert "secret" in rendered

def test_load_file_with_comments_and_interpolation(tmp_path, fresh_stec):
    source = """
    # runtime switches
    var dev = true  # flip for prod
    var pool = 10

    expose int port = 8080
    expose bool debug = $dev
    expose string dsn = "postgres://localhost:5432/app?pool=${pool}"
    """
    Stec.load(write_config(tmp_path, source))

    assert Stec.as_dict() == {
        "port": 8080,
        "debug": True,
        "dsn": "postgres://localhost:5432/app?pool=10",
    }
