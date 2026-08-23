"""duckboard: file-first local SQL workspace powered by DuckDB."""

from duckboard.exceptions import DuckboardError
from duckboard.session import DuckboardSession

__version__ = "0.2.0"

__all__ = [
    "DuckboardSession",
    "DuckboardError",
]
