# vim: ft=python fileencoding=utf-8 sw=4 et sts=4

# This file is part of vimiv.
# Copyright 2017-2019 Christian Karl (karlch) <karlch at protonmail dot com>
# License: GNU GPL v3, see the "LICENSE" and "AUTHORS" files for details.

import pytest_bdd as bdd

from vimiv.imutils import filelist
from vimiv.gui import mainwindow


bdd.scenarios("imagetitle.feature")


@bdd.then("the image name should be in the window title")
def image_name_in_title():
    assert filelist.basename() in mainwindow.instance().windowTitle()
