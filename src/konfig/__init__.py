"""konfig: typed, expressive configuration in a tiny dependency-free language."""

from .config import Konfig as _KonfigClass
from .errors import (
    KonfigAlreadyLoadedError,
    KonfigError,
    KonfigLoadError,
    KonfigNameError,
    KonfigSyntaxError,
    KonfigTypeError,
)

#: Global singleton instance: ``Konfig.load(...)`` then read values anywhere.
Konfig = _KonfigClass()

__version__ = "0.1.0"

__all__ = [
    "Konfig",
    "KonfigAlreadyLoadedError",
    "KonfigError",
    "KonfigLoadError",
    "KonfigNameError",
    "KonfigSyntaxError",
    "KonfigTypeError",
    "__version__",
]
