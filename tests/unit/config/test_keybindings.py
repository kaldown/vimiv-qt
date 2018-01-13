# vim: ft=python fileencoding=utf-8 sw=4 et sts=4

# This file is part of vimiv.
# Copyright 2017-2018 Christian Karl (karlch) <karlch at protonmail dot com>
# License: GNU GPL v3, see the "LICENSE" and "AUTHORS" files for details.

"""Tests for vimiv.config.keybindings."""

from vimiv.config import keybindings


def test_add_keybinding():
    @keybindings.add("t", "test")
    def test():
        pass
    bindings = keybindings.get("global")
    assert ("t", "test") in bindings.items()