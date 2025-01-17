# vim: ft=python fileencoding=utf-8 sw=4 et sts=4

# This file is part of vimiv.
# Copyright 2017-2019 Christian Karl (karlch) <karlch at protonmail dot com>
# License: GNU GPL v3, see the "LICENSE" and "AUTHORS" files for details.

"""Classes to deal with the actual image file."""

import logging
import os
import tempfile
from typing import List

from PyQt5.QtCore import QObject, QRunnable, QThreadPool, QCoreApplication
from PyQt5.QtGui import QPixmap, QImageReader, QMovie

from vimiv import api, utils, imutils
from vimiv.imutils import imtransform, immanipulate
from vimiv.utils import files

# We need the check as svg support is optional
try:
    from PyQt5.QtSvg import QSvgWidget
except ImportError:
    QSvgWidget = None


class Pixmaps:
    """Simple storage class for different pixmap versions.

    Class Attributes:
        current: The current possibly transformed and manipulated pixmap.
        original: The original unedited pixmap.
        transformed: The possibly transformed but unmanipulated pixmap.
    """

    current = None
    original = None
    transformed = None


class ImageFileHandler(QObject):
    """Handler to load and write images.

    The handler connects to the new_image_opened signal to retrieve the path of
    the current image. This path is opened with QImageReader and depending on
    the type of image one of the loaded signals is emitted with the generated
    QWidget. In addition to the loading the file handler provides a write
    command and is able to automatically write changes from transform or
    manipulate to file if wanted.

    Attributes:
        transform: Transform class to get rotate and flip from.
        manipulate: Manipulate class for e.g. brightness.

        _path: Path to the currently loaded QObject.
        _pixmaps: Pixmaps object storing different version of the loaded image.
    """

    _pool = QThreadPool.globalInstance()

    @api.objreg.register
    def __init__(self):
        super().__init__()
        self._pixmaps = Pixmaps()

        self.transform = imtransform.Transform(self)
        self.manipulate = immanipulate.Manipulator(self)

        self._path = ""

        imutils.new_image_opened.connect(self._on_new_image_opened)
        imutils.all_images_cleared.connect(self._on_images_cleared)
        imutils.image_changed.connect(self.reload)
        QCoreApplication.instance().aboutToQuit.connect(self._on_quit)

    @property
    def current(self):
        """The currently displayed pixmap.

        Upon setting a signal to update the image shown is emitted.
        """
        return self._pixmaps.current

    @current.setter
    def current(self, pixmap):
        self._pixmaps.current = pixmap
        reload_only = True
        imutils.pixmap_loaded.emit(pixmap, reload_only)

    @property
    def original(self):
        """Original pixmap without any transformation or manipulations.

        Upon setting all edited pixmaps are reset as well.
        """
        return self._pixmaps.original

    @original.setter
    def original(self, pixmap) -> None:
        self._pixmaps.original = (
            self._pixmaps.transformed
        ) = self._pixmaps.current = pixmap

    @property
    def transformed(self):
        """Transformed pixmap without any manipulations applied.

        Upon setting the current pixmap gets updated and shown.
        """
        return self._pixmaps.transformed

    @transformed.setter
    def transformed(self, pixmap):
        self._pixmaps.transformed = pixmap
        self.current = pixmap

    @utils.slot
    def _on_new_image_opened(self, path: str):
        """Load proper displayable QWidget for a new image path."""
        self._maybe_write(self._path)
        self._load(path, reload_only=False)

    @utils.slot
    def _on_images_cleared(self):
        """Reset to default when all images were cleared."""
        self._path = ""
        self.original = None

    @api.commands.register(mode=api.modes.IMAGE)
    def reload(self):
        """Reload the current image."""
        self._load(self._path, reload_only=True)

    def _maybe_write(self, path):
        """Write image to disk if requested and it has changed.

        Args:
            path: Path to the image file.
        """
        if not api.settings.image.autowrite:
            self._reset()
        elif self.transform.changed() or self.manipulate.changed():
            self.write_pixmap(self.current, path, path)

    @utils.slot
    def _on_quit(self):
        """Possibly write changes to disk on quit."""
        self._maybe_write(self._path)
        self._pool.waitForDone(5000)  # Kill writing after 5s

    def _load(self, path: str, reload_only: bool):
        """Load proper displayable QWidget for a path.

        This reads the image using QImageReader and then emits the appropriate
        *_loaded signal to tell the image to display a new object.
        """
        # Pass file format explicitly as imghdr does a much better job at this than the
        # file name based approach of QImageReader
        file_format = files.imghdr.what(path)
        if file_format is None:
            logging.error("%s is not a valid image", path)
            return
        reader = QImageReader(path, file_format.encode("utf-8"))
        reader.setAutoTransform(True)  # Automatically apply exif orientation
        if not reader.canRead():
            logging.error("Cannot read image %s", path)
            return
        # SVG
        if file_format == "svg" and QSvgWidget:
            # Do not store image and only emit with the path as the
            # VectorGraphic widget needs the path in the constructor
            self.original = None
            imutils.svg_loaded.emit(path, reload_only)
        # Gif
        elif reader.supportsAnimation():
            movie = QMovie(path)
            if not movie.isValid() or movie.frameCount() == 0:
                logging.error("Error reading animation %s: invalid data", path)
                return
            self.original = movie
            imutils.movie_loaded.emit(self.current, reload_only)
        # Regular image
        else:
            pixmap = QPixmap.fromImageReader(reader)
            if reader.error():
                logging.error("Error reading image %s: %s", path, reader.errorString())
                return
            self.original = pixmap
            imutils.pixmap_loaded.emit(self.current, reload_only)
        self._path = path

    def _reset(self):
        self.transform.reset()
        self.manipulate.reset()

    @api.commands.register(mode=api.modes.IMAGE)
    def write(self, path: List[str]):
        """Save the current image to disk.

        **syntax:** ``:write [path]``.

        positional arguments:
            * ``path``: Save to this path instead of the current one.
        """
        assert isinstance(path, list), "Must be list from nargs"
        path = " ".join(path) if path else self._path
        self.write_pixmap(self.current, path, self._path)

    def write_pixmap(self, pixmap, path, original_path):
        """Write a pixmap to disk.

        Args:
            pixmap: The QPixmap to write.
            path: The path to save the pixmap to.
            original_path: Original path of the opened pixmap.
        """
        runner = WriteImageRunner(pixmap, path, original_path)
        self._pool.start(runner)
        self._reset()


class WriteImageRunner(QRunnable):
    """Write QPixmap to file in an extra thread.

    This requires both the path to write to and the original path as Exif data
    may be copied from the original path to the new copy. The procedure is to
    write the path to a temporary file first, transplant the Exif data to the
    temporary file if possible and finally rename the temporary file to the
    final path. The renaming is done as it is an atomic operation and we may be
    overriding the existing file.

    Attributes:
        _pixmap: The QPixmap to write.
        _path: Path to write the pixmap to.
        _original_path: Original path of the opened pixmap.
    """

    def __init__(self, pixmap, path, original_path):
        super().__init__()
        self._pixmap = pixmap
        self._path = path
        self._original_path = original_path

    def run(self):
        """Write image to file."""
        logging.info("Saving %s...", self._path)
        try:
            self._can_write()
            logging.debug("Image is writable")
            self._write()
            logging.info("Saved %s", self._path)
        except WriteError as e:
            logging.error(str(e))

    def _can_write(self):
        """Check if it is possible to save the current path.

        Raises:
            WriteError if writing is not possible.
        """
        if not isinstance(self._pixmap, QPixmap):
            raise WriteError("Cannot write animations")
        if os.path.exists(self._path):  # Override current path
            reader = QImageReader(self._path)
            if not reader.canRead():
                raise WriteError("Path '%s' exists and is not an image" % (self._path))

    def _write(self):
        """Write pixmap to disk."""
        # Get pixmap type
        _, ext = os.path.splitext(self._path)
        # First create temporary file and then move it to avoid race conditions
        handle, filename = tempfile.mkstemp(dir=os.getcwd(), suffix=ext)
        os.close(handle)
        self._pixmap.save(filename)
        # Copy exif info from original file to new file
        imutils.exif.copy_exif(self._original_path, filename)
        os.rename(filename, self._path)
        # Check if valid image was created
        if not os.path.isfile(self._path):
            raise WriteError("File not written, unknown exception")
        if not files.is_image(self._path):
            os.remove(self._path)
            raise WriteError("No valid image written. Is the extention valid?")


class WriteError(Exception):
    """Raised when the WriteImageRunner encounters problems."""
