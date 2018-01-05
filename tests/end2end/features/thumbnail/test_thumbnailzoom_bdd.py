# vim: ft=python fileencoding=utf-8 sw=4 et sts=4

# This file is part of vimiv.
# Copyright 2017-2018 Christian Karl (karlch) <karlch at protonmail dot com>
# License: GNU GPL v3, see the "LICENSE" and "AUTHORS" files for details.

import pytest_bdd as bdd

from vimiv.config import settings
from vimiv.utils import objreg


bdd.scenarios("thumbnailzoom.feature")


@bdd.then(bdd.parsers.parse("the thumbnail size should be {size}"))
def check_thumbnail_size(size):
    size = int(size)
    # Check setting
    assert settings.get_value("thumbnail.size") == size
    # Check actual value
    thumb = objreg.get("thumbnail")
    assert thumb.iconSize().width() == size