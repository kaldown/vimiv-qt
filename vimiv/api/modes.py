# vim: ft=python fileencoding=utf-8 sw=4 et sts=4

# This file is part of vimiv.
# Copyright 2017-2019 Christian Karl (karlch) <karlch at protonmail dot com>
# License: GNU GPL v3, see the "LICENSE" and "AUTHORS" files for details.

"""`Default modes and utility functions for mode handling`.

Similar to vim, vimiv has the concept of ``modes``. The same command or
keybinding can perform different actions depending on the mode it is executed
in. Each mode is assigned to a ``QWidget`` class which is focused when this
mode is active. To assign a widget to a mode, the :func:`widget` decorator is
used.

The following modes exist:

    * IMAGE
    * LIBRARY
    * THUMBNAIL
    * COMMAND
    * MANIPULATE

In addition there is the special ``GLOBAL`` mode which corresponds to
``IMAGE``, ``LIBRARY`` and ``THUMBNAIL``. When adding commands for this mode,
they are automatically added for each of these three modes.

All modes inherit from the common :class:`Mode` base class.
"""


import abc
import logging
from typing import cast, Any, Callable, List

from PyQt5.QtCore import pyqtSignal, QObject
from PyQt5.QtWidgets import QWidget

from vimiv.utils import AbstractQObjectMeta


class NoMode(Exception):
    """Raised when there is no mode to operate on."""


class Mode(QObject, metaclass=AbstractQObjectMeta):
    """Base class for modes.

    Class Attributes:
        _ID: Unique identifier used to compare modes.

    Attributes:
        active: True if the mode is currently active.
        last_fallback: Mode to use as _last in case _last was closed.
        widget: QWidget associated with this mode.

        _last: Mode that was active before entering this one.
        _name: Name of the mode used for commands which require a string
            representation.
        _id: The unique identifier used to compare modes.

    Signals:
        entered: Emitted when this mode is entered.
        left: Emitted when this mode is left.
    """

    entered = pyqtSignal()
    left = pyqtSignal()

    _ID = 0

    def __init__(self, name: str):
        super().__init__()
        self.active = False
        self.last_fallback = cast(Mode, None)  # Initialized to a mode in _init()
        self.widget = cast(QWidget, None)  # Initialized to a QWidget using @widget

        self._last = cast(Mode, None)  # Initialized to a mode in _init()
        self._name = name

        # Store global ID as ID and increase it by one
        self._id = Mode._ID
        Mode._ID += 1

    def enter(self) -> None:
        """Enter this mode."""
        last_mode = current()
        # Nothing to do as we all already in this mode
        if last_mode == self:
            logging.debug("Staying in mode %s", self.name)
            return
        # Store last mode
        if last_mode:
            logging.debug("Leaving mode %s", last_mode.name)
            last_mode.active = False
            self.last = last_mode
        # Set to active and focus widget
        self.active = True
        self.widget.show()
        self.widget.setFocus()
        if self.widget.hasFocus():
            logging.debug("%s widget focused", self)
        else:
            logging.debug("Could not focus %s widget", self)
        self.entered.emit()
        logging.debug("Entered mode %s", self)

    def leave(self) -> None:
        """Leave this mode for the last mode."""
        self.last.enter()
        self.left.emit()
        # Reset the last mode when leaving a specific mode as leaving means closing
        # the widget and we do not want to re-open a closed widget implicitly
        self.last.reset_last()

    def toggle(self) -> None:
        """Toggle this mode.

        If the mode is currently visible, leave it. Otherwise enter it.
        """
        if self.widget.isVisible():
            self.leave()
        else:
            self.enter()

    @property
    def identifier(self) -> int:
        """Value of _id to compare to other modes as property."""
        return self._id

    @property
    def last(self) -> "Mode":
        """Mode that was active before this one.

        Setting this property must be implemented by the child class.  This is required
        as in command mode, any mode can be the last mode which is supposed to be
        focused when leaving the command line, but e.g. in library mode when toggling
        the library we should never enter manipulate.
        """
        return self._last

    @last.setter
    def last(self, mode: "Mode") -> None:
        self._set_last(mode)  # To be implemented by the child class

    def reset_last(self) -> None:
        """Reset last mode to the fallback value.

        This can be used when the last mode was closed.
        """
        self._last = self.last_fallback

    @abc.abstractmethod
    def _set_last(self, mode: "Mode") -> None:
        pass

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Mode):
            return self.identifier == other.identifier
        return False

    def __hash__(self) -> int:
        return self._id

    @property
    def name(self) -> str:
        """Name of this mode as read-only property."""
        return self._name

    def __repr__(self) -> str:
        return "Mode.%s" % (self.name.upper())


def get_by_name(name: str) -> Mode:
    """Retrieve Mode class by name.

    This can be used in case the python :class:`vimiv.api.modes.Mode` class is
    not available, for example when running commands.

    Args:
        name: Name of the mode to retrieve.
    Returns:
        The corresponding :class:`vimiv.api.modes.Mode` class.
    """
    for mode in ALL:
        if mode.name.lower() == name.lower():
            return mode
    raise KeyError("'%s' is not a valid mode" % (name.upper()))


def widget(mode: Mode) -> Callable:
    """Decorator to assign a widget to a mode.

    The decorator decorates the __init__ function of a QWidget class storing
    the created component as the widget associated to the mode. This is used
    when entering a mode to focus the widget which is assigned to this mode.

    Example::

        class ImageWidget:

        @modes.widget(modes.IMAGE)
        def __init__(self):
            ...

    Args:
        mode: The mode to associate the decorated widget with.
    """

    def decorator(component_init: Callable) -> Callable:
        def inner(component: Any, *args: Any, **kwargs: Any) -> None:
            mode.widget = component
            component_init(component, *args, **kwargs)

        return inner

    return decorator


class _MainMode(Mode):
    """Main mode class used for everything but command mode."""

    def _set_last(self, mode: Mode) -> None:
        """Store any mode except for command and manipulate."""
        if mode not in [COMMAND, MANIPULATE]:
            self._last = mode


class _CommandMode(Mode):
    """Command mode class."""

    def _set_last(self, mode: Mode) -> None:
        """Store any mode except for command."""
        if mode != self:
            self._last = mode


# Create all modes
GLOBAL = _MainMode("global")
IMAGE = _MainMode("image")
LIBRARY = _MainMode("library")
THUMBNAIL = _MainMode("thumbnail")
COMMAND = _CommandMode("command")
MANIPULATE = _MainMode("manipulate")


# Utility lists to allow iterating
ALL: List[Mode] = [GLOBAL, IMAGE, LIBRARY, THUMBNAIL, COMMAND, MANIPULATE]
GLOBALS: List[Mode] = [IMAGE, LIBRARY, THUMBNAIL]


def current() -> Mode:
    """Return the currently active mode."""
    for mode in ALL:
        if mode.active:
            return mode
    raise NoMode()


def _init() -> None:
    """Initialize default values for each mode."""
    for _mode in ALL:
        if _mode == IMAGE:
            _mode.active = True  # Default mode
            _mode.last = _mode.last_fallback = LIBRARY
        else:
            _mode.last = _mode.last_fallback = IMAGE


_init()
