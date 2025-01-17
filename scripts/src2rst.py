#!/usr/bin/env python3

# This file is part of vimiv.
# Copyright 2017-2019 Christian Karl (karlch) <karlch at protonmail dot com>
# License: GNU GPL v3, see the "LICENSE" and "AUTHORS" files for details.

# This file is part of vimiv.
# Copyright 2017-2018 Christian Karl (karlch) <karlch at protonmail dot com>
# License: GNU GPL v3, see the "LICENSE" and "AUTHORS" files for details.
# vim: ft=python fileencoding=utf-8 sw=4 et sts=4

"""Generate reST documentation from source code docstrings."""

import inspect
import importlib
import os
import sys

from vimiv import startup, api

from rstutils import RSTFile


def generate_status_modules():
    """Generate table overview of status modules."""
    print("generating statusbar modules...")
    filename = "docs/documentation/configuration/status_modules.rstsrc"
    with RSTFile(filename) as f:
        rows = [("Module", "Description")]
        for name in sorted(api.status._modules.keys()):
            func = api.status._modules[name]._func
            name = name.strip("{}")
            desc = inspect.getdoc(func).split("\n")[0]
            rows.append((name, desc))
        f.write_table(rows, title="Overview of status modules", widths="30 70")


def _write_command_description(cmds, mode, f):
    """Write description of docstring of commands to documentation file."""
    for name in sorted(cmds.keys()):
        cmd = cmds[name]
        f.write("\n.. _ref_%s_%s:\n\n" % (mode, name))
        f.write_subsubsection(name)
        doc = inspect.getdoc(cmd.func)
        f.write("%s\n\n" % (doc))


def generate_commands():
    """Generate table overview and description of the commands."""
    print("generating commands...")
    with RSTFile("docs/documentation/commands_desc.rstsrc") as f:
        for mode, cmds in api.commands._registry.items():
            f.write_subsection(mode.name.capitalize())
            # Table of command overview
            rows = [("Command", "Description")]
            title = "Overview of %s commands" % (mode.name)
            for name in sorted(cmds.keys()):
                cmd = cmds[name]
                link = ":ref:`ref_%s_%s`" % (mode.name, name)
                rows.append((link, cmd.description))
            f.write_table(rows, title=title, widths="25 75")
            _write_command_description(cmds, mode.name, f)


def generate_settings():
    """Generate table overview of all settings."""
    print("generating settings...")
    filename = "docs/documentation/configuration/settings_table.rstsrc"
    with RSTFile(filename) as f:
        rows = [("Setting", "Description")]
        for name in sorted(api.settings._storage.keys()):
            setting = api.settings._storage[name]
            if setting.desc:  # Otherwise the setting is meant to be hidden
                rows.append((name, setting.desc))
        f.write_table(rows, title="Overview of settings", widths="30 70")


def generate_keybindings():
    """Generate table overview of default keybindings."""
    print("generating keybindings...")
    filename = "docs/documentation/configuration/keybindings_table.rstsrc"
    with RSTFile(filename) as f:
        for mode, bindings in api.keybindings.items():
            rows = _gen_keybinding_rows(bindings)
            title = "Keybindings for %s mode" % (mode.name)
            f.write_table(rows, title=title, widths="20 80")


def _gen_keybinding_rows(bindings):
    """Generate rows for keybindings table."""
    rows = [("Keybinding", "Command")]
    for binding, command in bindings.items():
        rows.append(("\\%s" % (binding), command))
    return sorted(rows, key=lambda row: row[1])


def generate_commandline_options():
    """Generate file including the command line options."""
    parser = startup.get_argparser()
    optionals, positionals, titles = _get_options(parser)
    # Synopsis
    filename_synopsis = "docs/manpage/synopsis.rstsrc"
    with open(filename_synopsis, "w") as f:
        synopsis_options = ["[%s]" % (title) for title in titles]
        synopsis = "**vimiv** %s" % (" ".join(synopsis_options))
        f.write(synopsis)
    # Options
    filename_options = "docs/manpage/options.rstsrc"
    with RSTFile(filename_options) as f:
        f.write_section("positional arguments")
        f.write(positionals)
        f.write_section("optional arguments")
        f.write(optionals)


def _get_options(parser):
    """Retrieve the options from the argument parser.

    Returns:
        optionals: Formatted string of optional arguments.
        positionals: Formatted string of positional arguments.
        titles: List containing all argument titles.
    """
    optionals = ""
    positionals = ""
    titles = []
    for action in parser._optionals._actions:
        if not action.option_strings:
            positionals += _format_positional(action, titles)
        else:
            optionals += _format_optional(action, titles)
    return optionals, positionals, titles


def _format_optional(action, titles):
    """Format optional argument neatly.

    Args:
        action: The argparser action.
        titles: List of titles to update with the title(s) of this argument.
    Returns:
        Formatted string of this argument.
    """
    _titles = _format_optional_title(action)
    titles.extend(_titles)
    title = ", ".join(_titles)
    desc = action.help
    return _format_option(title, desc)


def _format_positional(action, titles):
    """Format positional argument neatly.

    Args:
        action: The argparser action.
        titles: List of titles to update with the title of this argument.
    Returns:
        Formatted string of this argument.
    """
    title = "**%s**" % (action.metavar)
    titles.append(title)
    desc = action.help
    return _format_option(title, desc)


def _format_option(title, desc):
    """Format an option neatly.

    Args:
        title: The title of this option.
        desc: The help description of this option.
    """
    return "%s\n\n    %s\n\n" % (title, desc)


def _format_optional_title(action):
    """Format the title of an optional argument neatly.

    The title depends on the number of arguments this action requires.

    Args:
        action: The argparser action.
    Returns:
        Formatted title string of this argument.
    """
    formats = []
    for option in action.option_strings:
        if isinstance(action.metavar, str):  # One argument
            title = "**%s** *%s*" % (option, action.metavar)
        elif isinstance(action.metavar, tuple):  # Multiple arguments
            elems = ["*%s*" % (elem) for elem in action.metavar]
            title = "**%s** %s" % (option, " ".join(elems))
        else:  # No arguments
            title = "**%s**" % (option)
        formats.append(title)
    return formats


def generate_plugins():
    """Generate overview table of default plugins."""
    print("generating default plugins...")

    filename = "docs/documentation/configuration/default_plugins.rstsrc"
    plugins_directory = "vimiv/plugins"
    sys.path.insert(0, plugins_directory)

    plugin_names = sorted(
        [
            filename.replace(".py", "")
            for filename in os.listdir(plugins_directory)
            if not filename.startswith("_") and filename.endswith(".py")
        ]
    )

    def get_plugin_description(name):
        module = importlib.import_module(name, plugins_directory)
        docstring = inspect.getdoc(module)
        return docstring.split("\n")[0].strip(" .")

    rows = [("Name", "Description")]
    for name in plugin_names:
        rows.append((name, get_plugin_description(name)))

    with RSTFile(filename) as f:
        f.write_table(rows, title="Overview of default plugins", widths="20 80")


if __name__ == "__main__":
    generate_status_modules()
    generate_commands()
    generate_settings()
    generate_keybindings()
    generate_commandline_options()
    generate_plugins()
