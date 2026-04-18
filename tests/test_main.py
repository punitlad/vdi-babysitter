"""Tests for vdi_babysitter/main.py"""

from unittest.mock import patch
from typer.testing import CliRunner
from vdi_babysitter.main import app

runner = CliRunner()


def test_no_args_shows_help():
    result = runner.invoke(app, [])
    assert result.exit_code in (0, 2)
    assert "citrix" in result.output
    assert "configure" in result.output
    assert "use" in result.output


def test_use_sets_active_profile():
    with patch("vdi_babysitter.main.set_active_profile") as mock_set:
        result = runner.invoke(app, ["use", "work"])
    assert result.exit_code == 0
    mock_set.assert_called_once_with("work")


def test_use_requires_profile_argument():
    result = runner.invoke(app, ["use"])
    assert result.exit_code != 0
