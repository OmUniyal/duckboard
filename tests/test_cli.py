from __future__ import annotations

import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest

from duckboard.cli import main


# ---------------------------------------------------------------------------
# 1. --version prints version and exits 0
# ---------------------------------------------------------------------------
def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        with patch("sys.argv", ["duckboard", "--version"]):
            main()
    assert exc.value.code == 0
    # argparse prints version to stdout
    captured = capsys.readouterr()
    assert "duckboard" in captured.out


# ---------------------------------------------------------------------------
# 2. --help exits 0
# ---------------------------------------------------------------------------
def test_help_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        with patch("sys.argv", ["duckboard", "--help"]):
            main()
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert ":load" in captured.out
    assert ":tables" in captured.out


# ---------------------------------------------------------------------------
# 3. No args launches REPL with a DuckboardSession
# ---------------------------------------------------------------------------
def test_no_args_launches_repl():
    with (
        patch("sys.argv", ["duckboard"]),
        patch("duckboard.cli.run_repl") as mock_repl,
        patch("duckboard.cli.DuckboardSession") as mock_session_cls,
    ):
        mock_session = MagicMock()
        mock_session_cls.return_value.__enter__.return_value = mock_session
        mock_session_cls.return_value.__exit__.return_value = False
        main()
    mock_repl.assert_called_once_with(mock_session)