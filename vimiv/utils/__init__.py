# vim: ft=python fileencoding=utf-8 sw=4 et sts=4

# This file is part of vimiv.
# Copyright 2017-2019 Christian Karl (karlch) <karlch at protonmail dot com>
# License: GNU GPL v3, see the "LICENSE" and "AUTHORS" files for details.

"""Various utility functions."""

import cProfile
import functools
import inspect
import logging
import re
from abc import ABCMeta
from contextlib import contextmanager, suppress
from datetime import datetime
from pstats import Stats
from typing import Callable, Optional, TypeVar, List, Any

from PyQt5.QtCore import pyqtSlot

# Different location under PyQt < 5.11
try:
    from PyQt5.sip import wrappertype  # type: ignore
except ImportError:
    from sip import wrappertype  # type: ignore


Number = TypeVar("Number", int, float)


def add_html(tag: str, text: str) -> str:
    """Surround text in a html tag.

    Args:
        tag: Tag to use, e.g. b.
        text: The text to surround.
    """
    return "<%s>%s</%s>" % (tag, text, tag)


def wrap_style_span(style: str, text: str) -> str:
    """Surround text in a html style span tag.

    Args:
        style: The css style content to use.
        text: The text to surround.
    """
    return f"<span style='{style};'>{text}</span>"


def strip_html(text: str) -> str:
    """Strip all html tags from text.

    strip("<b>hello</b>") = "hello"

    Returns:
        The stripped text.
    """
    stripper = re.compile("<.*?>")
    return re.sub(stripper, "", text)


def clamp(
    value: Number, minimum: Optional[Number], maximum: Optional[Number]
) -> Number:
    """Clamp a value so it does not exceed boundaries."""
    if minimum is not None:
        value = max(value, minimum)
    if maximum is not None:
        value = min(value, maximum)
    return value


def class_that_defined_method(method):
    """Return the class that defined a method.

    This is used by the decorators for statusbar and command, when the class is
    not yet created.
    """
    return getattr(inspect.getmodule(method), method.__qualname__.split(".")[0])


def is_method(func):
    """Return True if func is a method owned by a class.

    This is used by the decorators for statusbar and command, when the class is
    not yet created.
    """
    return "self" in inspect.signature(func).parameters


def cached_method(func):
    """Decorator to cache the result of a class method."""
    attr_name = "_lazy_" + func.__name__

    @property
    @functools.wraps(func)
    def _lazyprop(self):
        def inner(*args, **kwargs):
            # Store the result of the function to attr_name in first
            # evaluation, afterwards return the cached value
            if not hasattr(self, attr_name):
                setattr(self, attr_name, func(self, *args, **kwargs))
            return getattr(self, attr_name)

        return inner

    return _lazyprop


class AnnotationNotFound(Exception):
    """Raised if a there is no type annotation to use."""

    def __init__(self, name: str, function: Callable):
        message = "Missing type annotation for parameter '%s' in function '%s'" % (
            name,
            function.__qualname__,
        )
        super().__init__(message)


def _slot_args(argspec, function):
    """Create arguments for pyqtSlot from function arguments.

    Args:
        argspec: Function arguments retrieved via inspect.
        function: The python function for which the arguments are created.
    Returns:
        List of types of the function arguments as arguments for pyqtSlot.
    """
    slot_args = []
    for argument in argspec.args:
        has_annotation = argument in argspec.annotations
        if argument == "self" and not has_annotation:
            continue
        if not has_annotation:
            raise AnnotationNotFound(argument, function)
        annotation = argspec.annotations[argument]
        slot_args.append(annotation)
    return slot_args


def _slot_kwargs(argspec):
    """Add return type to slot kwargs if it exists."""
    with suppress(KeyError):
        return_type = argspec.annotations["return"]
        if return_type is not None:
            return {"result": return_type}
    return {}


def slot(function):
    """Annotation based slot decorator using pyqtSlot.

    Syntactic sugar for pyqtSlot so the parameter types do not have to be repeated when
    there are type annotations.

    Example:
        @slot
        def function(self, x: int, y: int) -> None:
        ...
    """
    argspec = inspect.getfullargspec(function)
    slot_args, slot_kwargs = _slot_args(argspec, function), _slot_kwargs(argspec)
    pyqtSlot(*slot_args, **slot_kwargs)(function)
    return function


def flatten(list_of_lists: List[List[Any]]) -> List[Any]:
    """Flatten a list of lists into a single list with all elements."""
    return [elem for sublist in list_of_lists for elem in sublist]


def remove_prefix(text: str, prefix: str) -> str:
    """Remove a prefix of a given string."""
    if text.startswith(prefix):
        return text[len(prefix) :]
    return text


class AbstractQObjectMeta(wrappertype, ABCMeta):
    """Metaclass to allow setting to be an ABC as well as a QObject."""


def timed(function):
    """Decorator to time a function and log evaluation time."""

    def inner(*args, **kwargs):
        """Wrap decorated function and add timing."""
        start = datetime.now()
        return_value = function(*args, **kwargs)
        elapsed_in_ms = (datetime.now() - start).total_seconds() * 1000
        logging.info("%s: took %.3f ms", function.__qualname__, elapsed_in_ms)
        return return_value

    return inner


@contextmanager
def profile(amount: int = 15):
    """Contextmanager to profile code secions.

    Starts a cProfile.Profile upon entry, disables it on exit and prints profiling
    information.

    Usage:
        with profile(amount=10):
            # your code to profile here
            ...
        # This is no longer profiled

    Args:
        amount: Number of lines to restrict the output to.
    """
    cprofile = cProfile.Profile()
    cprofile.enable()
    yield
    cprofile.disable()
    stats = Stats(cprofile)
    stats.sort_stats("cumulative").print_stats(amount)
    stats.sort_stats("time").print_stats(amount)
