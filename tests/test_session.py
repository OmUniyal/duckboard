"""Tests for DuckboardSession."""

from duckboard import DuckboardSession


def test_session_opens_and_closes() -> None:
    with DuckboardSession() as session:
        assert session is not None
