"""stec: typed, expressive configuration in a tiny dependency-free language."""

from .config import Stec as _StecClass
from .errors import (
    StecAlreadyLoadedError,
    StecError,
    StecLoadError,
    StecNameError,
    StecSyntaxError,
    StecTypeError,
)

#: Global singleton instance: ``Stec.load(...)`` then read values anywhere.
Stec = _StecClass()

__version__ = "0.1.0"

__all__ = [
    "Stec",
    "StecAlreadyLoadedError",
    "StecError",
    "StecLoadError",
    "StecNameError",
    "StecSyntaxError",
    "StecTypeError",
    "__version__",
]
