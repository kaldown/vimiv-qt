# vim: ft=python fileencoding=utf-8 sw=4 et sts=4

# This file is part of vimiv.
# Copyright 2017-2019 Christian Karl (karlch) <karlch at protonmail dot com>
# License: GNU GPL v3, see the "LICENSE" and "AUTHORS" files for details.

import pytest
import pytest_bdd as bdd

from vimiv import api
from vimiv.gui import library, mainwindow


bdd.scenarios("libraryresize.feature")


@bdd.then(bdd.parsers.parse("the library width should be {fraction}"))
def check_library_size(fraction, qtbot):
    fraction = float(fraction)
    # Check if setting was updated
    assert api.settings.library.width.value == pytest.approx(fraction)
    # Check if width fits fraction of main window
    real_fraction = library.instance().width() / mainwindow.instance().width()
    assert fraction == real_fraction
