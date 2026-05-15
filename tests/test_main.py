"""Tests for vdi_babysitter/main.py"""

from unittest.mock import patch
from typer.testing import CliRunner
from vdi_babysitter.main import app

runner = CliRunner()


def test_no_args_shows_error():
    result = runner.invoke(app, [])
    assert result.exit_code == 1
    assert "Error: command argument required." in result.output
    assert "citrix" in result.output
    assert "configure" in result.output
    assert "use" in result.output


def test_version_stable():
    with patch("vdi_babysitter.main.__sha__", None):
        with patch("vdi_babysitter.main._pkg_version", return_value="1.0.1"):
            result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "v1.0.1" in result.output


def test_version_reads_from_version_file():
    from vdi_babysitter._version import __sha__
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.output.strip() == __sha__


def test_use_sets_active_profile():
    with patch("vdi_babysitter.main.set_active_profile") as mock_set:
        result = runner.invoke(app, ["use", "work"])
    assert result.exit_code == 0
    mock_set.assert_called_once_with("work")


def test_use_requires_profile_argument():
    result = runner.invoke(app, ["use"])
    assert result.exit_code != 0
