# vim: ft=python fileencoding=utf-8 sw=4 et sts=4

# This file is part of vimiv.
# Copyright 2017-2019 Christian Karl (karlch) <karlch at protonmail dot com>
# License: GNU GPL v3, see the "LICENSE" and "AUTHORS" files for details.

"""CommandLine widget in the bar."""

from contextlib import suppress

from PyQt5.QtCore import QCoreApplication, QTimer
from PyQt5.QtWidgets import QLineEdit

from vimiv import api, utils
from vimiv.commands import history, argtypes, runners, search
from vimiv.config import styles
from vimiv.utils import eventhandler


def _command_func(prefix, command, mode):
    """Return callable function for command depending on prefix."""
    if prefix == ":":
        return lambda: runners.run(command, mode=mode)
    # No need to search again if incsearch is enabled
    if prefix in "/?" and not search.use_incremental(mode):
        return lambda: search.search(command, mode, reverse=prefix == "?")
    return lambda: None


class UnknownPrefix(Exception):
    """Raised if a prefix in the command line is not known."""

    def __init__(self, prefix):
        """Call the parent with a generated message.

        Args:
            prefix: The unknown prefix.
        """
        message = "Unknown prefix '%s', possible values: %s" % (
            prefix,
            ", ".join(["'%s'" % (p) for p in CommandLine.PREFIXES]),
        )
        super().__init__(message)


class CommandLine(eventhandler.KeyHandler, QLineEdit):
    """Commandline widget in the bar.

    Class Attributes:
        PREFIXES: Possible prefixes for commands, e.g. ':' or '/'.

    Attributes:
        mode: Mode in which the command is run, corresponds to the mode from
            which the commandline was entered.

        _history: History object to store and interact with history.
    """

    PREFIXES = ":/?"

    STYLESHEET = """
    QLineEdit {
        font: {statusbar.font};
        background-color: {statusbar.bg};
        color: {statusbar.fg};
        border: 0px solid;
        padding: {statusbar.padding};
    }
    """

    @api.modes.widget(api.modes.COMMAND)
    @api.objreg.register
    def __init__(self):
        super().__init__()
        self._history = history.History(
            history.read(), max_items=api.settings.command_history_limit.value
        )
        self.mode = None

        self.returnPressed.connect(self._on_return_pressed)
        self.editingFinished.connect(self._history.reset)
        self.textEdited.connect(self._on_text_edited)
        self.textChanged.connect(self._incremental_search)
        self.cursorPositionChanged.connect(self._on_cursor_position_changed)
        QCoreApplication.instance().aboutToQuit.connect(self._on_app_quit)
        api.modes.COMMAND.entered.connect(self._on_entered)

        styles.apply(self)

    @utils.slot
    def _on_return_pressed(self) -> None:
        """Run command and store history on return."""
        prefix, command = self._split_prefix(self.text())
        if not command:  # Only prefix entered
            return
        # Write prefix to history as well for "separate" search history
        self._history.update(prefix + command)
        # Retrieve function to call depending on prefix
        func = _command_func(prefix, command, self.mode)
        # Run commands in QTimer so the command line has been left when the
        # command runs
        QTimer.singleShot(0, func)

    def _split_prefix(self, text):
        """Remove prefix from text for command processing.

        Returns:
            prefix: One of PREFIXES.
            command: Rest of the text stripped from whitespace.
        """
        prefix, command = text[0], text[1:]
        if prefix not in self.PREFIXES:
            raise UnknownPrefix(prefix)
        command = command.strip()
        return prefix, command

    @utils.slot
    def _on_text_edited(self, text: str) -> None:
        if not text:
            self.editingFinished.emit()
        else:
            self._history.reset()

    @utils.slot
    def _incremental_search(self) -> None:
        """Run incremental search if enabled."""
        if not search.use_incremental(self.mode):
            return
        with suppress(IndexError):  # Not enough text
            prefix, text = self._split_prefix(self.text())
            if prefix in "/?" and text:
                search.search(text, self.mode, reverse=prefix == "?", incremental=True)

    @utils.slot
    def _on_cursor_position_changed(self, _old: int, new: int):
        """Prevent the cursor from moving before the prefix."""
        if new < 1:
            self.setCursorPosition(1)

    @api.keybindings.register("<ctrl>p", "history next", mode=api.modes.COMMAND)
    @api.keybindings.register("<ctrl>n", "history prev", mode=api.modes.COMMAND)
    @api.commands.register(mode=api.modes.COMMAND)
    def history(self, direction: argtypes.HistoryDirection):
        """Cycle through command history.

        **syntax:** ``:history direction``

        positional arguments:
            * ``direction``: The direction to cycle in (next/prev).
        """
        self.setText(self._history.cycle(direction, self.text()))

    @api.keybindings.register(
        "<up>", "history-substr-search next", mode=api.modes.COMMAND
    )
    @api.keybindings.register(
        "<down>", "history-substr-search prev", mode=api.modes.COMMAND
    )
    @api.commands.register(mode=api.modes.COMMAND)
    def history_substr_search(self, direction: argtypes.HistoryDirection):
        """Cycle through command history with substring matching.

        **syntax:** ``:history-substr-search direction``

        positional arguments:
            * ``direction``: The direction to cycle in (next/prev).
        """
        self.setText(self._history.substr_cycle(direction, self.text()))

    @utils.slot
    def _on_app_quit(self):
        """Write command history to file on quit."""
        history.write(self._history)

    def focusOutEvent(self, event):
        """Override focus out event to not emit editingFinished."""

    @utils.slot
    def _on_entered(self):
        """Store mode from which the command line was entered."""
        self.mode = api.modes.COMMAND.last


def instance():
    return api.objreg.get(CommandLine)
