# vim: ft=python fileencoding=utf-8 sw=4 et sts=4

# This file is part of vimiv.
# Copyright 2017-2019 Christian Karl (karlch) <karlch at protonmail dot com>
# License: GNU GPL v3, see the "LICENSE" and "AUTHORS" files for details.

"""Thumbnail widget."""

import collections
import logging
import os
from typing import List, Optional

from PyQt5.QtCore import Qt, QSize, QItemSelectionModel, QModelIndex, QRect, pyqtSlot
from PyQt5.QtWidgets import QListWidget, QListWidgetItem, QStyle, QStyledItemDelegate
from PyQt5.QtGui import QColor, QIcon

from vimiv import api, utils, imutils
from vimiv.commands import argtypes, search
from vimiv.config import styles
from vimiv.utils import eventhandler, pixmap_creater, thumbnail_manager, clamp


class ThumbnailView(eventhandler.KeyHandler, QListWidget):
    """Thumbnail widget.

    Attributes:
        _paths: Last paths loaded to avoid duplicate loading.
        _highlighted: List of indices that are highlighted as search results.
        _sizes: Dictionary of thumbnail sizes with integer size as key and
            string name of the size as value.
        _default_thumb: Thumbnail to display before thumbnails were generated.
        _manager: ThumbnailManager class to create thumbnails asynchronously.
    """

    STYLESHEET = """
    QListWidget {
        font: {thumbnail.font};
        background-color: {thumbnail.bg};
    }

    QListWidget::item {
        padding: {thumbnail.padding}px;
    }

    QListWidget::item:selected {
        background: {thumbnail.selected.bg};
    }

    QListWidget QScrollBar {
        width: {library.scrollbar.width};
        background: {library.scrollbar.bg};
    }

    QListWidget QScrollBar::handle {
        background: {library.scrollbar.fg};
        border: {library.scrollbar.padding} solid
                {library.scrollbar.bg};
        min-height: 10px;
    }

    QListWidget QScrollBar::sub-line, QScrollBar::add-line {
        border: none;
        background: none;
    }
    """

    @api.modes.widget(api.modes.THUMBNAIL)
    @api.objreg.register
    def __init__(self):
        super().__init__()
        self._paths = []
        self._highlighted = []
        self._sizes = collections.OrderedDict(
            [(64, "small"), (128, "normal"), (256, "large"), (512, "x-large")]
        )
        self._default_icon = QIcon(pixmap_creater.default_thumbnail())
        self._manager = thumbnail_manager.ThumbnailManager()

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setViewMode(QListWidget.IconMode)
        default_size = api.settings.thumbnail.size.value
        self.setIconSize(QSize(default_size, default_size))
        self.setResizeMode(QListWidget.Adjust)

        self.setItemDelegate(ThumbnailDelegate(self))

        imutils.new_image_opened.connect(self._on_new_image_opened)
        imutils.new_images_opened.connect(self._on_new_images_opened)
        api.settings.thumbnail.size.changed.connect(self._on_size_changed)
        search.search.new_search.connect(self._on_new_search)
        search.search.cleared.connect(self._on_search_cleared)
        self._manager.created.connect(self._on_thumbnail_created)
        self.activated.connect(self._on_activated)
        api.mark.marked.connect(self._mark_highlight)
        api.mark.unmarked.connect(lambda path: self._mark_highlight(path, marked=False))

        styles.apply(self)

    @pyqtSlot(list)
    def _on_new_images_opened(self, paths: List[str]):
        """Load new paths into thumbnail widget.

        Args:
            paths: List of new paths to load.
        """
        if paths == self._paths:  # Nothing to do
            return
        # Delete paths that are no longer here
        # We must go in reverse order as otherwise the indexing changes on the
        # fly
        for i, path in enumerate(self._paths[::-1]):
            if path not in paths:
                if not self.takeItem(len(self._paths) - 1 - i):
                    logging.error("Error removing thumbnail for %s", path)
        # Add new paths
        for i, path in enumerate(paths):
            if path not in self._paths:
                item = QListWidgetItem(self, i)
                item.setSizeHint(QSize(self.item_size(), self.item_size()))
                item.setIcon(self._default_icon)
        # Update paths and create thumbnails
        self._paths = paths
        self._manager.create_thumbnails_async(paths)

    @utils.slot
    def _on_new_image_opened(self, path: str):
        self._select_item(self._paths.index(path))

    @utils.slot
    def _on_activated(self, index: QModelIndex):
        """Emit signal to update image index on activated.

        Args:
            index: QModelIndex activated.
        """
        self.open_selected()

    @utils.slot
    def _on_thumbnail_created(self, index: int, icon: QIcon):
        """Insert created thumbnail as soon as manager created it.

        Args:
            index: Index of the created thumbnail as integer.
            icon: QIcon to insert.
        """
        item = self.item(index)
        if item is not None:  # Otherwise it has been deleted in the meanwhile
            item.setIcon(icon)

    @pyqtSlot(int, list, api.modes.Mode, bool)
    def _on_new_search(
        self, index: int, matches: List[str], mode: api.modes.Mode, incremental: bool
    ):
        """Select search result after new search.

        Args:
            index: Index to select.
            matches: List of all matches of the search.
            mode: Mode for which the search was performed.
            incremental: True if incremental search was performed.
        """
        self._highlighted = []
        if self._paths and mode == api.modes.THUMBNAIL:
            self._select_item(index)
            for i, path in enumerate(self._paths):
                if os.path.basename(path) in matches:
                    self._highlighted.append(i)
            self.repaint()

    @utils.slot
    def _on_search_cleared(self):
        """Reset highlighted and force repaint when search results cleared."""
        self._highlighted = []
        self.repaint()

    def _mark_highlight(self, path: str, marked: bool = True):
        """(Un-)Highlight a path if it was (un-)marked.

        Args:
            path: The (un-)marked path.
            marked: True if it was marked.
        """
        try:
            index = self._paths.index(path)
        except ValueError:
            return
        item = self.item(index)
        # Set arbitrary text as the mark is highlighted by a rectangle
        item.setText("1" if marked else "")

    def is_highlighted(self, index):
        """Return True if the index is highlighted as search result."""
        return index.row() in self._highlighted

    @api.commands.register(mode=api.modes.THUMBNAIL)
    def open_selected(self):
        """Open the currently selected thumbnail in image mode."""
        imutils.load(self.abspath())
        api.modes.IMAGE.enter()

    @api.keybindings.register("k", "scroll up", mode=api.modes.THUMBNAIL)
    @api.keybindings.register("j", "scroll down", mode=api.modes.THUMBNAIL)
    @api.keybindings.register("h", "scroll left", mode=api.modes.THUMBNAIL)
    @api.keybindings.register("l", "scroll right", mode=api.modes.THUMBNAIL)
    @api.commands.register(mode=api.modes.THUMBNAIL)
    def scroll(self, direction: argtypes.Direction, count=1):
        """Scroll to another thumbnail in the given direction.

        **syntax:** ``:scroll direction``

        positional arguments:
            * ``direction``: The direction to scroll in (left/right/up/down).

        **count:** multiplier
        """
        current = self.currentRow()
        column = current % self.columns()
        if direction == argtypes.Direction.Right:
            current += 1 * count
            current = min(current, self.count() - 1)
        elif direction == argtypes.Direction.Left:
            current -= 1 * count
            current = max(0, current)
        elif direction == argtypes.Direction.Down:
            # Do not jump between columns
            current += self.columns() * count
            elems_in_last_row = self.count() % self.columns()
            if not elems_in_last_row:
                elems_in_last_row = self.columns()
            if column < elems_in_last_row:
                current = min(self.count() - (elems_in_last_row - column), current)
            else:
                current = min(self.count() - 1, current)
        else:
            current -= self.columns() * count
            current = max(column, current)
        self._select_item(current)

    @api.keybindings.register("gg", "goto 1", mode=api.modes.THUMBNAIL)
    @api.keybindings.register("G", "goto -1", mode=api.modes.THUMBNAIL)
    @api.commands.register(mode=api.modes.THUMBNAIL)
    def goto(self, index: int, count: Optional[int] = None):
        """Select specific thumbnail in current filelist.

        **syntax:** ``:goto index``


        positional arguments:
            * ``index``: Number of the thumbnail to select.

        .. hint:: -1 is the last thumbnail.

        **count:** Select [count]th thubnail instead.
        """
        index = count if count is not None else index  # Prefer count
        if index > 0:
            index -= 1  # Start indexing at 1
        index = index % self.count()
        self._select_item(index)

    @api.keybindings.register("-", "zoom out", mode=api.modes.THUMBNAIL)
    @api.keybindings.register("+", "zoom in", mode=api.modes.THUMBNAIL)
    @api.commands.register(mode=api.modes.THUMBNAIL)
    def zoom(self, direction: argtypes.Zoom):
        """Zoom the current widget.

        **syntax:** ``:zoom direction``

        positional arguments:
            * ``direction``: The direction to zoom in (in/out).

        **count:** multiplier
        """
        size = self.iconSize().width()
        size = size // 2 if direction == direction.Out else size * 2
        size = clamp(size, 64, 512)
        api.settings.thumbnail.size.value = size

    def rescale_items(self):
        """Reset item hint when item size has changed."""
        for i in range(self.count()):
            item = self.item(i)
            item.setSizeHint(QSize(self.item_size(), self.item_size()))
        self.scrollTo(self.selectionModel().currentIndex(), hint=self.PositionAtCenter)

    def _select_item(self, index):
        """Select specific item in the ListWidget.

        Args:
            index: Number of the current item to select.
        """
        index = self.model().index(index, 0)
        self._select_index(index)

    def _select_index(self, index):
        """Select specific index in the ListWidget.

        Args:
            index: QModelIndex to select.
        """
        selmod = QItemSelectionModel.Rows | QItemSelectionModel.ClearAndSelect
        self.selectionModel().setCurrentIndex(index, selmod)
        self.scrollTo(index, hint=self.PositionAtCenter)

    def _on_size_changed(self, value: int):
        self.setIconSize(QSize(value, value))
        self.rescale_items()

    def columns(self):
        """Return the number of columns."""
        sb_width = int(styles.get("image.scrollbar.width").replace("px", ""))
        return (self.width() - sb_width) // self.item_size()

    def item_size(self):
        """Return the size of one icon including padding."""
        padding = int(styles.get("thumbnail.padding").replace("px", ""))
        return self.iconSize().width() + 2 * padding

    @api.status.module("{thumbnail-name}")
    def current(self):
        """Name of the currently selected thumbnail."""
        try:
            abspath = self._paths[self.currentRow()]
            basename = os.path.basename(abspath)
            name, _ = os.path.splitext(basename)
            return name
        except IndexError:
            return ""

    def abspath(self):
        """Return the absolute path of the current thumbnail."""
        try:
            return self._paths[self.currentRow()]
        except IndexError:
            return ""

    @api.status.module("{thumbnail-size}")
    def size(self):
        """Current thumbnail size (small/normal/large/x-large)."""
        return self._sizes[self.iconSize().width()]

    @api.status.module("{thumbnail-index}")
    def index(self):
        """Index of the currently selected thumbnail."""
        return str(self.currentRow() + 1)

    @api.status.module("{thumbnail-total}")
    def total(self):
        """Total number of thumbnails."""
        return str(self.model().rowCount())

    def resizeEvent(self, event):
        """Update resize event to keep selected thumbnail centered."""
        super().resizeEvent(event)
        self.scrollTo(self.selectionModel().currentIndex(), hint=self.PositionAtCenter)


class ThumbnailDelegate(QStyledItemDelegate):
    """Delegate used for the thumbnail widget.

    The delegate draws the items.
    """

    def __init__(self, parent):
        super().__init__(parent)

        # QColor options for background drawing
        self.bg = QColor()
        self.bg.setNamedColor(styles.get("thumbnail.bg"))
        self.selection_bg = QColor()
        self.selection_bg.setNamedColor(styles.get("thumbnail.selected.bg"))
        self.search_bg = QColor()
        self.search_bg.setNamedColor(styles.get("thumbnail.search.highlighted.bg"))
        self.mark_bg = QColor()
        self.mark_bg.setNamedColor(styles.get("mark.color"))
        self.padding = int(styles.get("thumbnail.padding"))

    def paint(self, painter, option, index):
        """Override the QStyledItemDelegate paint function.

        Args:
            painter: The QPainter.
            option: The QStyleOptionViewItem.
            index: The QModelIndex.
        """
        self._draw_background(painter, option, index)
        self._draw_pixmap(painter, option, index)

    def _draw_background(self, painter, option, index):
        """Draw the background rectangle of the thumbnail.

        The color depends on whether the item is selected and on whether it is
        highlighted as a search result.

        Args:
            painter: The QPainter.
            option: The QStyleOptionViewItem.
            index: The QModelIndex.
        """
        color = self._get_background_color(index, option.state)
        painter.save()
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        painter.drawRect(option.rect)
        painter.restore()

    def _draw_pixmap(self, painter, option, index):
        """Draw the actual pixmap of the thumbnail.

        This calculates the size of the pixmap, applies padding and
        appropriately centers the image.

        Args:
            painter: The QPainter.
            option: The QStyleOptionViewItem.
            index: The QModelIndex.
        """
        painter.save()
        # Original thumbnail pixmap
        pixmap = self.parent().item(index.row()).icon().pixmap(256)
        # Rectangle that can be filled by the pixmap
        rect = QRect(
            option.rect.x() + self.padding,
            option.rect.y() + self.padding,
            option.rect.width() - 2 * self.padding,
            option.rect.height() - 2 * self.padding,
        )
        # Size the pixmap should take
        size = pixmap.size().scaled(rect.size(), Qt.KeepAspectRatio)
        # Coordinates to center the pixmap
        diff_x = (rect.width() - size.width()) / 2.0
        diff_y = (rect.height() - size.height()) / 2.0
        x = option.rect.x() + self.padding + diff_x
        y = option.rect.y() + self.padding + diff_y
        # Draw
        painter.drawPixmap(x, y, size.width(), size.height(), pixmap)
        painter.restore()
        self._draw_mark(painter, index, option, x + size.width(), y + size.height())

    def _draw_mark(self, painter, index, option, x, y):
        """Draw small rectangle as mark indicator if the image is marked.

        Args:
            painter: The QPainter.
            option: The QStyleOptionViewItem.
            index: The QModelIndex.
            x: x-coordinate at which the pixmap ends.
            y: y-coordinate at which the pixmap ends.
        """
        if not index.model().data(index):  # Thumbnail not marked
            return
        # Try to set 5 % of width, reduce to padding if this is smaller
        # At least 4px width
        width = max(min(0.05 * option.rect.width(), self.padding), 4)
        painter.save()
        painter.setBrush(self.mark_bg)
        painter.setPen(Qt.NoPen)
        painter.drawRect(x - 0.5 * width, y - 0.5 * width, width, width)
        painter.restore()

    def _get_background_color(self, index, state):
        """Return the background color of an item.

        The color depends on selected and highlighted as search result.

        Args:
            index: Index of the element indicating even/odd/highlighted.
            state: State of the index indicating selected.
        """
        if state & QStyle.State_Selected:
            return self.selection_bg
        if self.parent().is_highlighted(index):
            return self.search_bg
        return self.bg


def instance():
    return api.objreg.get(ThumbnailView)
