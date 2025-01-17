# vim: ft=python fileencoding=utf-8 sw=4 et sts=4

# This file is part of vimiv.
# Copyright 2017-2019 Christian Karl (karlch) <karlch at protonmail dot com>
# License: GNU GPL v3, see the "LICENSE" and "AUTHORS" files for details.

"""bdd-like steps for end2end testing."""

import os

from PyQt5.QtCore import Qt, QThreadPool
from PyQt5.QtWidgets import QApplication

import pytest_bdd as bdd

from vimiv import api
from vimiv.commands import runners
from vimiv.gui import commandline, statusbar, mainwindow, library, thumbnail
from vimiv.imutils import filelist


###############################################################################
#                                    When                                     #
###############################################################################


@bdd.when(bdd.parsers.parse("I run {command}"))
def run_command(command):
    runners.run(command, mode=api.modes.current())


@bdd.when(bdd.parsers.parse("I press {keys}"))
def key_press(qtbot, keys):
    mode = api.modes.current()
    qtbot.keyClicks(mode.widget, keys)


@bdd.when("I activate the command line")
def activate_commandline(qtbot):
    """Needed as passing return as a string is not possible."""
    qtbot.keyClick(commandline.instance(), Qt.Key_Return)
    qtbot.wait(10)


@bdd.when(bdd.parsers.parse("I enter {mode} mode"))
def enter_mode(mode):
    api.modes.get_by_name(mode).enter()


@bdd.when(bdd.parsers.parse("I leave {mode} mode"))
def leave_mode(mode):
    api.modes.get_by_name(mode).leave()


@bdd.when(bdd.parsers.parse('I enter command mode with "{text}"'))
def enter_command_with_text(text):
    api.modes.COMMAND.enter()
    commandline.instance().setText(":" + text)
    commandline.instance().textEdited.emit(":" + text)


@bdd.when(bdd.parsers.parse("I resize the window to {size}"))
def resize_main_window(size):
    width = int(size.split("x")[0])
    height = int(size.split("x")[1])
    mainwindow.instance().resize(width, height)


@bdd.when(bdd.parsers.parse("I wait for {N}ms"))
def wait(qtbot, N):
    qtbot.wait(int(N))


@bdd.when("I wait for the command to complete")
def wait_for_external_command(qtbot):
    """Wait until the external process has completed."""
    max_iterations = 100
    iteration = 0
    while (
        QThreadPool.globalInstance().activeThreadCount() and iteration < max_iterations
    ):
        qtbot.wait(10)
        iteration += 1
    assert iteration != max_iterations, "external command timed out"


###############################################################################
#                                    Then                                     #
###############################################################################


@bdd.then("no crash should happen")
def no_crash(qtbot):
    """Don't do anything, exceptions fail the test anyway."""
    qtbot.wait(0.01)


@bdd.then(bdd.parsers.parse("the message\n'{message}'\nshould be displayed"))
def check_statusbar_message(qtbot, message):
    bar = statusbar.statusbar
    _check_status(
        qtbot,
        lambda: message == bar["message"].text(),
        info=f"Message expected: '{message}'",
    )
    assert bar["stack"].currentWidget() == bar["message"]


@bdd.then(bdd.parsers.parse("the {position} status should include {text}"))
def check_left_status(qtbot, position, text):
    bar = statusbar.statusbar
    _check_status(
        qtbot,
        lambda: text in bar[position].text(),
        info=f"position {position} should include {text}",
    )
    assert bar["stack"].currentWidget() == bar["status"]


@bdd.then("a message should be displayed")
def check_a_statusbar_message(qtbot):
    bar = statusbar.statusbar
    _check_status(
        qtbot, lambda: bar["message"].text() != "", info="Any message expected"
    )
    assert bar["stack"].currentWidget() == bar["message"]


@bdd.then("no message should be displayed")
def check_no_statusbar_message(qtbot):
    bar = statusbar.statusbar
    _check_status(
        qtbot, lambda: bar["message"].text() == "", info="No message expected"
    )
    assert bar["stack"].currentWidget() == bar["status"]


@bdd.then(bdd.parsers.parse("the working directory should be {basename}"))
def check_working_directory(basename):
    assert os.path.basename(os.getcwd()) == basename


@bdd.then("the window should be fullscreen")
def check_fullscreen():
    assert mainwindow.instance().isFullScreen()


@bdd.then("the window should not be fullscreen")
def check_not_fullscreen():
    assert not mainwindow.instance().isFullScreen()


@bdd.then(bdd.parsers.parse("the mode should be {mode}"))
def check_mode(mode, qtbot):
    mode = api.modes.get_by_name(mode)
    assert api.modes.current() == mode, "Modehandler did not switch to %s" % (mode.name)


@bdd.then(bdd.parsers.parse("the library row should be {row}"))
def check_row_number(row):
    assert library.instance().row() + 1 == int(row)


@bdd.then(bdd.parsers.parse("the image should have the index {index}"))
def check_image_index(index):
    assert filelist.get_index() == index


@bdd.given("I enter thumbnail mode")
def enter_thumbnail():
    api.modes.THUMBNAIL.enter()
    thumbnail.instance().setFixedWidth(400)  # Make sure width is as expected


@bdd.then(bdd.parsers.parse("the thumbnail number {N} should be selected"))
def check_selected_thumbnail(qtbot, N):
    thumb = thumbnail.instance()
    assert thumb.currentRow() + 1 == int(N)


@bdd.then(bdd.parsers.parse("the pop up '{title}' should be displayed"))
def check_popup_displayed(title):
    for window in QApplication.topLevelWindows():
        if window.title() == title:
            window.close()
            return
    raise AssertionError(f"Window '{title}' not found")


@bdd.then(bdd.parsers.parse("the filelist should contain {number} images"))
def check_filelist_length(number):
    assert filelist.total() == number


def _check_status(qtbot, assertion, info=""):
    """Check statusbar repeatedly as this is threaded and may take a while."""
    iteration = 0
    max_iterations = 100
    while not assertion() and iteration < max_iterations:
        qtbot.wait(10)
        iteration += 1
    assert iteration != max_iterations, "Statusbar check timed out\n" + info
