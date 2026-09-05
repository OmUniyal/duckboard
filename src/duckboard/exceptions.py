"""Duckboard exception hierarchy."""


class DuckboardError(Exception):
    """Base error for duckboard."""


class CatalogError(DuckboardError):
    """Raised when file registration or table lookup fails."""

class TerminalTooNarrowError(DuckboardError):
    """Raised when the terminal is too narrow to render a table horizontally."""

class CommandError(DuckboardError):
    """Raised when a meta-command (:load, :save, etc.) fails."""
