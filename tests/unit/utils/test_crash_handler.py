# vim: ft=python fileencoding=utf-8 sw=4 et sts=4

# This file is part of vimiv.
# Copyright 2017-2019 Christian Karl (karlch) <karlch at protonmail dot com>
# License: GNU GPL v3, see the "LICENSE" and "AUTHORS" files for details.

"""Tests for vimiv.utils.crash_handler."""

import logging
import functools
import signal
import sys
import types
from contextlib import suppress
from collections import namedtuple

import pytest

from vimiv.utils import crash_handler


@pytest.fixture
def print_logging():
    """Fixture to reassign logging to stdout for easier capturing."""
    info, error, fatal = logging.info, logging.error, logging.fatal
    logging.info = logging.error = logging.fatal = functools.partial(print, end="")
    yield
    logging.info, logging.error, logging.fatal = info, error, fatal


@pytest.fixture
def handler(mocker, print_logging):
    """Fixture to set up the crash handler with a mock app and mock excepthook."""
    initial_excepthook = sys.excepthook
    mock_excepthook = mocker.Mock()
    sys.excepthook = mock_excepthook
    app = mocker.Mock()
    instance = crash_handler.CrashHandler(app)
    yield namedtuple("HandlerFixture", ["instance", "app", "excepthook"])(
        instance, app, mock_excepthook
    )
    sys.excepthook = initial_excepthook


def test_crash_handler_updates_excepthook(handler):
    assert not isinstance(sys.excepthook, types.BuiltinFunctionType)


def test_crash_handler_excepthook(capsys, handler):
    # Call system exceptook with some error
    error = ValueError("Not a number")
    sys.excepthook(type(error), error, None)
    # Check log output
    captured = capsys.readouterr()
    assert (
        captured.out == "Uncaught exception! Exiting gracefully and printing stack..."
    )
    # Check default excepthook called
    assert handler.excepthook.called_once_with((type(error), error, None))
    # Check if graceful quit was called
    assert handler.app.exit.called_once_with(1)


def test_crash_handler_exception_in_excepthook(capsys, handler):
    # Setup app exit to throw an exception
    def broken(_returncode):
        raise KeyError("I lost something")

    handler.app.exit = broken
    # Call system exceptook with some error checking for system exit
    error = ValueError("Not a number")
    with pytest.raises(SystemExit, match="42"):
        sys.excepthook(type(error), error, None)
    # Check log output
    captured = capsys.readouterr()
    assert "I lost something" in captured.out
    assert "suicide" in captured.out


def test_crash_handler_first_interrupt(capsys, handler):
    handler.instance.handle_interrupt(signal.SIGINT, None)
    # Check log output
    captured = capsys.readouterr()
    assert "SIGINT/SIGTERM" in captured.out
    # Check if graceful quit was called
    assert handler.app.exit.called_once_with(signal.SIGINT + 128)
    # Check if more forceful handler was installed
    assert (
        signal.getsignal(signal.SIGINT)
        == signal.getsignal(signal.SIGTERM)
        == handler.instance.handle_interrupt_forcefully
    )


def test_crash_handler_second_interrupt(capsys, handler):
    # Check if sys.exit is called with the correct return code
    with pytest.raises(SystemExit, match=str(128 + signal.SIGINT)):
        handler.instance.handle_interrupt_forcefully(signal.SIGINT, None)
    # Check log output
    captured = capsys.readouterr()
    assert "kill signal" in captured.out
