"""Tests for the Konfig singleton."""

import pytest

from konfig import (
    Konfig,
    KonfigAlreadyLoadedError,
    KonfigLoadError,
    KonfigSyntaxError,
)

GOOD = """
var dev = true

expose int port = 8080
expose string url = $dev ? "127.0.0.1" : "0.0.0.0"
"""


@pytest.fixture()
def fresh_konfig():
    Konfig.reset()
    yield
    Konfig.reset()


def write_config(tmp_path, text):
    path = tmp_path / "app.konfig"
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_load_and_access_everywhere(tmp_path, fresh_konfig):
    Konfig.load(write_config(tmp_path, GOOD))

    assert Konfig.is_loaded
    assert Konfig.port == 8080
    assert Konfig["url"] == "127.0.0.1"
    assert Konfig.get("port") == 8080
    assert Konfig.get("missing") is None
    assert Konfig.get("missing", 5) == 5
    assert Konfig.as_dict() == {"port": 8080, "url": "127.0.0.1"}
    assert "port" in Konfig
    assert "dev" not in Konfig


def test_vars_are_hidden_from_public_api(tmp_path, fresh_konfig):
    Konfig.load(write_config(tmp_path, GOOD))

    with pytest.raises(AttributeError):
        Konfig.dev  # noqa: B018
    with pytest.raises(KeyError):
        Konfig["dev"]
    assert "dev" not in Konfig.as_dict()


def test_konfig_is_a_true_singleton(fresh_konfig):
    from konfig.config import Konfig as KonfigClass

    assert KonfigClass() is Konfig
    assert KonfigClass() is KonfigClass()


def test_load_returns_the_singleton(tmp_path, fresh_konfig):
    assert Konfig.load(write_config(tmp_path, GOOD)) is Konfig


def test_double_load_without_force_raises(tmp_path, fresh_konfig):
    path = write_config(tmp_path, GOOD)
    Konfig.load(path)

    with pytest.raises(KonfigAlreadyLoadedError) as error:
        Konfig.load(path)
    assert "already loaded" in str(error.value)


def test_force_reload_picks_up_changes(tmp_path, fresh_konfig):
    path = write_config(tmp_path, GOOD)
    Konfig.load(path)

    write_config(tmp_path, "expose int port = 9090")
    Konfig.load(path, force=True)

    assert Konfig.port == 9090
    assert "url" not in Konfig.as_dict()
    assert Konfig.loaded_from == path


def test_load_missing_file(tmp_path, fresh_konfig):
    with pytest.raises(KonfigLoadError):
        Konfig.load(str(tmp_path / "missing.konfig"))


def test_load_file_with_syntax_error(tmp_path, fresh_konfig):
    with pytest.raises(KonfigSyntaxError):
        Konfig.load(write_config(tmp_path, "var broken = @"))


def test_failed_load_does_not_mark_singleton_as_loaded(tmp_path, fresh_konfig):
    with pytest.raises(KonfigSyntaxError):
        Konfig.load(write_config(tmp_path, "var broken = @"))

    assert not Konfig.is_loaded

    Konfig.load(write_config(tmp_path, GOOD))
    assert Konfig.port == 8080


def test_reset_clears_state(tmp_path, fresh_konfig):
    Konfig.load(write_config(tmp_path, GOOD))
    Konfig.reset()

    assert not Konfig.is_loaded
    with pytest.raises(AttributeError):
        Konfig.port  # noqa: B018


def test_repr_does_not_leak_values(tmp_path, fresh_konfig):
    Konfig.load(write_config(tmp_path, 'expose string secret = "topsecret"'))

    rendered = repr(Konfig)
    assert "topsecret" not in rendered
    assert "secret" in rendered
