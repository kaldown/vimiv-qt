# vim: ft=python fileencoding=utf-8 sw=4 et sts=4

# This file is part of vimiv.
# Copyright 2017-2019 Christian Karl (karlch) <karlch at protonmail dot com>
# License: GNU GPL v3, see the "LICENSE" and "AUTHORS" files for details.

"""Simple hello world greeting as example plugin.

The plugin defines a new command :hello-world which simply prints a message to the
terminal. The init and cleanup functions also print messages to the terminal without
further usage for demonstration purposes.
"""

from vimiv import api


@api.commands.register()
def hello_world() -> None:
    """Simple dummy function printing 'Hello world'."""
    print("Hello world")


def init() -> None:
    print("Initializing demo plugin")


def cleanup() -> None:
    print("Cleaning up demo plugin")
