# vim: ft=python fileencoding=utf-8 sw=4 et sts=4

# This file is part of vimiv.
# Copyright 2017-2019 Christian Karl (karlch) <karlch at protonmail dot com>
# License: GNU GPL v3, see the "LICENSE" and "AUTHORS" files for details.

import pytest_bdd as bdd

from vimiv import api
from vimiv.commands import runners


bdd.scenarios("fail_run_command.feature")


@bdd.when("I run")
def run_empty_command():
    runners.run("", mode=api.modes.current())
