"""Meta-commands: :load, :tables, :schema, :save, etc."""

from __future__ import annotations

from duckboard.session import DuckboardSession


def handle_command(command: str, session: DuckboardSession) -> str:
    """Dispatch a :command. Full implementation coming in commands phase."""
    return f"Unknown command: {command}"