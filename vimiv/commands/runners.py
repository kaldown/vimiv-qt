# vim: ft=python fileencoding=utf-8 sw=4 et sts=4

# This file is part of vimiv.
# Copyright 2017-2019 Christian Karl (karlch) <karlch at protonmail dot com>
# License: GNU GPL v3, see the "LICENSE" and "AUTHORS" files for details.

"""Classes and functions to run commands.

Module Attributes:
    external: ExternalRunner instance to run shell commands.

    _last_command: Dictionary storing the last command for each mode.
"""

import logging
import os
import re
import shlex
import subprocess
from typing import Dict, List, NamedTuple, Optional

from PyQt5.QtCore import QRunnable, QObject, QThreadPool, pyqtSignal

from vimiv import app, api, utils
from vimiv.commands import aliases
from vimiv.utils import pathreceiver


_last_command: Dict[api.modes.Mode, "LastCommand"] = {}


class LastCommand(NamedTuple):
    """Simple class storing command text, arguments and count."""

    Count: int
    Command: str
    Arguments: List[str]


def run(text, count=None, mode=None):
    """Run either external or internal command.

    Args:
        text: Complete text given to command line or keybinding.
        count: Count given if any.
        mode: Mode to run the command in.
    """
    text = text.strip()
    if not text:
        return
    text = _update_command(text, mode=mode)
    if text.startswith("!"):
        external(text.lstrip("!"))
    else:
        count = str(count) if count is not None else ""
        command(count + text, mode)


def _update_command(text, mode):
    """Update command with aliases and percent wildcard.

    Args:
        text: String passed as command.
        mode: Mode in which the command is supposed to run.
    """
    return expand_percent(alias(text, mode), mode)


def command(text, mode=None):
    """Run internal command when called.

    Splits the given text into count, name and arguments. Then runs the
    command corresponding to name with count and arguments. Emits the
    exited signal when done.

    Args:
        text: String passed as command.
        mode: Mode in which the command is supposed to run.
    """
    try:
        count, cmdname, args = _parse(text)
    except ValueError as e:  # E.g. raised by shlex on unclosed quotation
        logging.error("Error parsing command: %s", e)
        return
    mode = mode if mode is not None else api.modes.current()
    _run_command(count, cmdname, args, mode)
    logging.debug("Ran '%s' succesfully", text)


@api.keybindings.register(".", "repeat-command")
@api.commands.register(store=False)
def repeat_command(count: Optional[int] = None):
    """Repeat the last command.

    **count:** Repeat count times.
    """
    mode = api.modes.current()
    if mode not in _last_command:
        raise api.commands.CommandError("No command to repeat")
    stored_count, cmdname, args = _last_command[mode]
    # Prefer entered count over stored count
    count = count if count is not None else stored_count
    _run_command(count, cmdname, args, mode)


def _run_command(count, cmdname, args, mode):
    """Run a given command.

    Args:
        count: Count to use for the command.
        cmdname: Name of the command passed.
        args: Arguments passed.
        mode: Mode to run the command in.
    """
    try:
        cmd = api.commands.get(cmdname, mode)
        if cmd.store:
            _last_command[mode] = LastCommand(count, cmdname, args)
        cmd(args, count=count)
        api.status.update()
    except api.commands.CommandNotFound as e:
        logging.error(str(e))
    except (api.commands.ArgumentError, api.commands.CommandError) as e:
        logging.error("%s: %s", cmdname, str(e))
    except api.commands.CommandWarning as w:
        logging.warning("%s: %s", cmdname, str(w))


def _parse(text):
    """Parse given command text into count, name and arguments.

    Args:
        text: String passed as command.
    Returns:
        count: Digits prepending the command to interpret as count.
        name: Name of the command passed.
        args: Arguments passed.
    """
    text = text.strip()
    count = ""
    split = shlex.split(text)
    cmdname = split[0]
    # Receive prepended digits as count
    while cmdname and cmdname[0].isdigit():
        count += cmdname[0]
        cmdname = cmdname[1:]
    args = split[1:]
    return count, cmdname, args


def expand_percent(text, mode):
    """Expand % to the corresponding path and %m to all marked paths.

    Args:
        text: The command in which the wildcards are expanded.
        mode: Mode the command is run in to get correct path(-list).
    """
    # Check first as the re substitutions are rather expensive
    if "%m" in text:
        text = re.sub(r"(?<!\\)%m", " ".join(api.mark.paths), text)
    if "%" in text:
        current = shlex.quote(pathreceiver.current(mode))
        text = re.sub(r"(?<!\\)%", current, text)
    return text


class ExternalRunner(QObject):
    """Runner for external commands.

    Signals:
        pipe_output_received: Emitted when :!command | completes.
            arg1: The shell command that was executed.
            arg2: stdout of the shell command.
    """

    _pool = QThreadPool.globalInstance()
    pipe_output_received = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self.pipe_output_received.connect(self._on_pipe_output_received)

    def __call__(self, text):
        """Run external command using ShellCommandRunnable.

        Args:
            text: Text parsed as command to run.
        """
        runnable = ShellCommandRunnable(text, self)
        self._pool.start(runnable)

    @utils.slot
    def _on_pipe_output_received(self, cmd: str, stdout: str):
        """Open paths from stdout.

        Args:
            cmd: Executed shell command.
            stdout: String form of stdout of the exited shell command.
        """
        paths = [path for path in stdout.split("\n") if os.path.exists(path)]
        try:
            app.open(paths)
            logging.debug("Opened paths from pipe '%s'", cmd)
            api.status.update()
        except api.commands.CommandError:
            logging.warning("%s: No paths from pipe", cmd)


external = ExternalRunner()


class ShellCommandRunnable(QRunnable):
    """Run shell command in an extra thread.

    Captures stdout and stderr. Logging is called according to the returncode
    of the command.

    Attributes:
        _text: Text parsed as command to run.
        _runner: ExternalRunner that started this runnable.
        _pipe: Whether to check stdout for paths to open.
    """

    def __init__(self, text, runner):
        super().__init__()
        self._text = text.rstrip("|").strip()
        self._runner = runner
        self._pipe = bool(text.endswith("|"))

    def run(self):
        """Run shell command on QThreadPool.start(self)."""
        try:
            pargs = subprocess.run(
                self._text,
                shell=True,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if self._pipe:
                self._runner.pipe_output_received.emit(
                    self._text, pargs.stdout.decode()
                )
            else:
                logging.debug("Ran '!%s' succesfully", self._text)
        except subprocess.CalledProcessError as e:
            message = e.stderr.decode().split("\n")[0]
            logging.error("%d  %s", e.returncode, message)


def alias(text, mode):
    """Replace alias with the actual command.

    Returns:
        The replaced text if text was an alias else text.
    """
    cmd = text.split()[0]
    if cmd in aliases.get(mode):
        return text.replace(cmd, aliases.get(mode)[cmd])
    return text
