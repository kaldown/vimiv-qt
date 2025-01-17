# vim: ft=python fileencoding=utf-8 sw=4 et sts=4

# This file is part of vimiv.
# Copyright 2017-2019 Christian Karl (karlch) <karlch at protonmail dot com>
# License: GNU GPL v3, see the "LICENSE" and "AUTHORS" files for details.

"""Handler for uncaught exceptions and signals."""

import functools
import logging
import os
import signal
import sys

from PyQt5.QtCore import QTimer, QSocketNotifier, QObject

# Fails on windows
# We do not officially support windows currently, but might do so in the future
try:
    import fcntl
except ImportError:
    # Mypy does not approve that we assigne None to a module but that is exactly what we
    # want to do for the optional import
    fcntl = None  # type: ignore


class CrashHandler(QObject):
    """Handler for uncaught exceptions and signals.

    Attributes:
        _app: Main vimiv application to exit from.
    """

    def __init__(self, app):
        super().__init__()
        self._app = app
        # Setup signal handling
        _assign_interrupt_handler(self.handle_interrupt)
        if fcntl is not None:  # unix-like systems
            self._setup_wakeup_fd()
        else:
            self._setup_timer()
        # Setup hook for uncaught exceptions
        sys.excepthook = functools.partial(self.handle_exception, sys.excepthook)
        # Finalize
        logging.debug("Initialized crash handler")

    def _setup_wakeup_fd(self):
        """Set up wakeup filedescriptor for signal handling.

        This returns the control from the Qt main loop in C++ back to python and allows
        signal handling in python. Only available for unix-like systems.
        """
        logging.debug("Setting up wakeup filedescriptor for unix-like systems")
        read_fd, write_fd = os.pipe()
        for fd in (read_fd, write_fd):
            flags = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        notifier = QSocketNotifier(read_fd, QSocketNotifier.Read, self)
        notifier.activated.connect(lambda: None)
        signal.set_wakeup_fd(write_fd)

    def _setup_timer(self, timeout=1000):
        """Set up a timer for signal handling.

        The timer gets called every timeout ms and returns the control from the Qt main
        loop in C++ back to python and allows signal handling in python. Available on
        all systems, especially windows.

        Args:
            timeout: Timeout in seconds after which the timer is repeatedly invoked.
        """
        logging.debug("Setting up timer for non unix systems")
        timer = QTimer()
        timer.start(timeout)
        timer.timeout.connect(lambda: None)

    def handle_exception(self, initial_handler, exc_type, exc_value, traceback):
        """Custom exception handler for uncaught exceptions.

        In addition to the standard python exception handler a log message is called and
        the application tries to exit gracefully.
        """
        logging.error("Uncaught exception! Exiting gracefully and printing stack...")
        initial_handler(exc_type, exc_value, traceback)
        try:
            self._app.exit(1)
        # We exit immediately by killing the application if an error in the graceful
        # exit occurs
        except Exception as e:  # pylint: disable=broad-except
            logging.fatal(
                "Uncaught exception in graceful exit... Committing suicide :("
            )
            logging.fatal("Exception: %r", e)
            sys.exit(42)

    def handle_interrupt(self, signum, _frame):
        """Initial handler for interrupt signals to exit gracefully.

        Args:
            signum: Signal number of the interrupt signal retrieved.
        """
        logging.debug("Interrupt handler called with signal %d", signum)
        _assign_interrupt_handler(self.handle_interrupt_forcefully)
        logging.info("SIGINT/SIGTERM received, exiting gracefully...")
        logging.info("To kill the process repeat the signal")
        QTimer.singleShot(0, functools.partial(self._app.exit, 128 + signum))

    def handle_interrupt_forcefully(self, signum, _frame):
        """Second handler for interrupt signals to exit forcefully.

        Args:
            signum: Signal number of the interrupt signal retrieved.
        """
        logging.debug("Interrupt handler called a second time with %d", signum)
        logging.fatal("Forceful kill signal retrieved... Hello darkness my old friend")
        sys.exit(128 + signum)


def _assign_interrupt_handler(handler):
    """Assign handler function to interrupt-like signals."""
    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)
