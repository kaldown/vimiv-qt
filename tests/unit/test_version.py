# vim: ft=python fileencoding=utf-8 sw=4 et sts=4

# This file is part of vimiv.
# Copyright 2017-2019 Christian Karl (karlch) <karlch at protonmail dot com>
# License: GNU GPL v3, see the "LICENSE" and "AUTHORS" files for details.

"""Tests for vimiv.version."""

import piexif

import pytest

from vimiv import version


@pytest.fixture
def no_svg_support():
    initial_value, version.QSvgWidget = version.QSvgWidget, None
    yield
    version.QSvgWidget = initial_value


@pytest.fixture
def no_exif_support():
    initial_value, version.piexif = version.piexif, None
    yield
    version.piexif = initial_value


def test_svg_support_info():
    assert "svg support: true" in version.info().lower()


def test_no_svg_support_info(no_svg_support):
    assert "svg support: false" in version.info().lower()


def test_exif_support_info():
    assert piexif.VERSION in version.info()


def test_no_exif_support_info(no_exif_support):
    assert "piexif: none" in version.info().lower()
