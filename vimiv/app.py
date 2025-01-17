# vim: ft=python fileencoding=utf-8 sw=4 et sts=4

# This file is part of vimiv.
# Copyright 2017-2019 Christian Karl (karlch) <karlch at protonmail dot com>
# License: GNU GPL v3, see the "LICENSE" and "AUTHORS" files for details.

"""Main application class using QApplication."""

import logging
import os
from typing import List

from PyQt5.QtCore import QThreadPool
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import QApplication

import vimiv
from vimiv import api, imutils
from vimiv.utils import files, working_directory


class Application(QApplication):
    """Main application class."""

    @api.objreg.register
    def __init__(self):
        """Initialize the main Qt application."""
        super().__init__([vimiv.__name__])  # Only pass program name to Qt
        self.setApplicationVersion(vimiv.__version__)
        self.setDesktopFileName(vimiv.__name__)
        self._set_icon()

    @api.keybindings.register("q", "quit")
    @api.commands.register()
    def quit(self):
        """Quit vimiv."""
        self.exit(0)

    def exit(self, returncode):
        """Exit the main application with returncode."""
        # Do not start any new threads
        QThreadPool.globalInstance().clear()
        # Wait for any running threads to exit safely
        QThreadPool.globalInstance().waitForDone()
        super().exit(returncode)

    def _set_icon(self):
        """Set window icon of vimiv."""
        logging.debug("Trying to retrieve icon from theme")
        icon = QIcon.fromTheme(vimiv.__name__)
        if icon.isNull():
            logging.debug("Trying to retrieve icon from project directory")
            icon = self._icon_from_project_directory()
            if icon.isNull():
                logging.error("Failed loading icon")
                return
        self.setWindowIcon(icon)

    def _icon_from_project_directory(self):
        """Try to retrieve the icon from the icons folder.

        Useful if vimiv was not installed but is used from the git project.
        """
        icon = QIcon()
        file_dir = os.path.realpath(os.path.dirname(__file__))
        project_dir = os.path.join(file_dir, os.pardir)
        icon_dir = os.path.join(project_dir, "icons")
        for size in (16, 32, 64, 128, 256, 512):
            path = os.path.join(icon_dir, f"vimiv_{size}x{size}.png")
            pixmap = QPixmap(path)
            icon.addPixmap(pixmap)
        return icon


# We want to use the name open here as it is the best name for the command
@api.keybindings.register("o", "command --text='open '")
@api.commands.register()
def open(paths: List[str]):  # pylint: disable=redefined-builtin
    """Open one or more paths.

    **syntax:** ``:open path [path ...]``

    If any path given is an image, all valid images are opened in image mode. Otherwise
    the first valid directory is opened. If both fails, an error is displayed.

    positional arguments:
        * ``paths``: The path(s) to open.
    """
    images, directories = files.supported(paths)
    mode = api.modes.LIBRARY
    if images:
        working_directory.handler.chdir(os.path.dirname(images[0]))
        imutils.load(*images)
        mode = api.modes.IMAGE
    elif directories:
        working_directory.handler.chdir(directories[0])
    else:
        raise api.commands.CommandError("No valid paths")
    mode.enter()


def instance():
    return api.objreg.get(Application)
