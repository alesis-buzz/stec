"""The Konfig singleton: load once, read everywhere."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Optional

from .errors import KonfigAlreadyLoadedError, KonfigLoadError
from .evaluator import evaluate
from .parser import parse


class Konfig:
    """Singleton registry of exposed configuration values.

    Calling ``Konfig()`` always returns the same shared object. The package
    exports one ready-made instance, so the usual usage is simply::

        from konfig import Konfig

        Konfig.load("app.konfig")

        Konfig.port          # attribute access
        Konfig["port"]       # item access
        Konfig.get("port")   # with optional default
        Konfig.as_dict()     # full snapshot
    """

    _instance: Optional["Konfig"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "Konfig":
        with cls._lock:
            if cls._instance is None:
                instance = super().__new__(cls)
                instance._values: dict[str, object] = {}
                instance._loaded_from: Optional[str] = None
                cls._instance = instance
        return cls._instance

    def load(self, path: str | Path, force: bool = False) -> "Konfig":
        """Parse and evaluate the file at *path* into the singleton.

        Raises ``KonfigAlreadyLoadedError`` if the configuration was already
        loaded unless *force* is set, which reloads it in place.
        """
        with Konfig._lock:
            if self._loaded_from is not None and not force:
                raise KonfigAlreadyLoadedError(
                    f"configuration already loaded from '{self._loaded_from}'; "
                    "pass force=True to reload"
                )
            source = self._read(path)
            document = parse(source)
            values = evaluate(document)
            self._values = values
            self._loaded_from = str(path)
        return self

    @staticmethod
    def _read(path: str | Path) -> str:
        try:
            return Path(path).read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise KonfigLoadError(f"cannot decode '{path}': not valid UTF-8") from error
        except OSError as error:
            reason = error.strerror or error.__class__.__name__
            raise KonfigLoadError(f"cannot read '{path}': {reason}") from error

    def reset(self) -> None:
        """Forget the loaded configuration (mainly useful in tests)."""
        with Konfig._lock:
            self._values = {}
            self._loaded_from = None

    @property
    def is_loaded(self) -> bool:
        """Whether a configuration file has been loaded."""
        return self._loaded_from is not None

    @property
    def loaded_from(self) -> Optional[str]:
        """Path the configuration was loaded from, if any."""
        return self._loaded_from

    def get(self, name: str, default: Any = None) -> Any:
        """Return the exposed value *name*, or *default* if absent."""
        return self._values.get(name, default)

    def as_dict(self) -> dict[str, object]:
        """Return a copy of all exposed values."""
        return dict(self._values)

    def __contains__(self, name: object) -> bool:
        return name in self._values

    def __getitem__(self, name: str) -> Any:
        try:
            return self._values[name]
        except KeyError:
            raise KeyError(f"konfig has no exposed value named {name!r}") from None

    def __getattr__(self, name: str) -> Any:
        values = self.__dict__.get("_values", {})
        if name in values:
            return values[name]
        raise AttributeError(f"konfig has no exposed value named {name!r}")

    def __repr__(self) -> str:
        keys = sorted(self._values)
        return f"Konfig(loaded_from={self._loaded_from!r}, keys={keys!r})"
