# vim: ft=python fileencoding=utf-8 sw=4 et sts=4

# This file is part of vimiv.
# Copyright 2017-2019 Christian Karl (karlch) <karlch at protonmail dot com>
# License: GNU GPL v3, see the "LICENSE" and "AUTHORS" files for details.

"""Completion widget in the bar."""

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QSizePolicy

from vimiv import api
from vimiv.config import styles
from vimiv.gui import widgets


class CompletionView(widgets.FlatTreeView):
    """Completion widget.

    Signals:
        activated: Emitted when the complete command was called.
            arg1: The selected completion text.
    """

    STYLESHEET = """
    QTreeView {
        font: {statusbar.font};
        color: {completion.fg};
        background-color: {completion.even.bg};
        alternate-background-color: {completion.odd.bg};
        outline: 0;
        border: 0px;
        padding: {statusbar.padding};
        min-height: {completion.height};
        max-height: {completion.height};
    }

    QTreeView::item:selected, QTreeView::item:selected:hover {
        color: {completion.selected.fg};
        background-color: {completion.selected.bg};
    }

    QTreeView QScrollBar {
        width: {completion.scrollbar.width};
        background: {completion.scrollbar.bg};
    }

    QTreeView QScrollBar::handle {
        background: {completion.scrollbar.fg};
        border: {completion.scrollbar.padding} solid
                {completion.scrollbar.bg};
        min-height: 10px;
    }

    QTreeView QScrollBar::sub-line, QScrollBar::add-line {
        border: none;
        background: none;
    }
    """

    activated = pyqtSignal(str)

    @api.objreg.register
    def __init__(self, parent):
        super().__init__(parent=parent)

        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)

        self.hide()

        styles.apply(self)

    def update_geometry(self, window_width, window_height):
        """Rescale width when main window was resized."""
        y = window_height - self.height()
        self.setGeometry(0, y, window_width, self.height())

    @api.keybindings.register(
        "<shift><tab>", "complete --inverse", mode=api.modes.COMMAND
    )
    @api.keybindings.register("<tab>", "complete", mode=api.modes.COMMAND)
    @api.commands.register(mode=api.modes.COMMAND)
    def complete(self, inverse: bool = False):
        """Invoke command line completion.

        **syntax:** ``:complete [--inverse]``

        optional arguments:
            * ``--inverse``: Complete in inverse direction.
        """
        try:
            row = self.row() - 1 if inverse else self.row() + 1
        except IndexError:  # First trigger of completion
            row = -1 if inverse else 0
        # No suggestions
        if not self.model().rowCount():
            return
        row = row % self.model().rowCount()
        self._select_row(row)
        index = self.selectionModel().selectedIndexes()[0]
        completion = index.data()
        self.activated.emit(completion)

    def resizeEvent(self, event):
        """Resize columns on resize event."""
        super().resizeEvent(event)
        self.update_column_widths()

    def update_column_widths(self):
        """Resize columnds according to model."""
        for i in range(self.model().columnCount()):
            fraction = self.model().sourceModel().column_widths[i]
            self.setColumnWidth(i, fraction * self.width())


def instance():
    return api.objreg.get(CompletionView)
