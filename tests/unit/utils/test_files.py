# vim: ft=python fileencoding=utf-8 sw=4 et sts=4

# This file is part of vimiv.
# Copyright 2017-2019 Christian Karl (karlch) <karlch at protonmail dot com>
# License: GNU GPL v3, see the "LICENSE" and "AUTHORS" files for details.

"""Tests for vimiv.utils.files."""

import os
import tarfile

from vimiv.utils import files


def test_listdir_wrapper(mocker):
    mocker.patch("os.listdir", return_value=["a.txt", "b.txt"])
    mocker.patch("os.path.abspath", return_value="")
    assert files.listdir("directory") == ["a.txt", "b.txt"]


def test_listdir_wrapper_returns_abspath(mocker):
    mocker.patch("os.listdir", return_value=["a.txt", "b.txt"])
    mocker.patch("os.path.abspath", return_value="dir")
    assert files.listdir("directory") == ["dir/a.txt", "dir/b.txt"]


def test_listdir_wrapper_sort(mocker):
    mocker.patch("os.listdir", return_value=["b.txt", "a.txt"])
    mocker.patch("os.path.abspath", return_value="")
    assert files.listdir("directory") == ["a.txt", "b.txt"]


def test_listdir_wrapper_remove_hidden(mocker):
    mocker.patch("os.listdir", return_value=[".dotfile.txt", "a.txt"])
    mocker.patch("os.path.abspath", return_value="")
    assert files.listdir("directory") == ["a.txt"]


def test_listdir_wrapper_show_hidden(mocker):
    mocker.patch("os.listdir", return_value=[".dotfile.txt", "a.txt"])
    mocker.patch("os.path.abspath", return_value="")
    assert files.listdir("directory", show_hidden=True) == [".dotfile.txt", "a.txt"]


def test_directories_supported(mocker):
    mocker.patch("os.path.isdir", return_value=True)
    mocker.patch("os.path.isfile", return_value=False)
    images, directories = files.supported(["a", "b"])
    assert not images
    assert directories == ["a", "b"]


def test_images_supported(mocker):
    mocker.patch("os.path.isdir", return_value=False)
    mocker.patch("os.path.isfile", return_value=True)
    mocker.patch("imghdr.what", return_value=True)
    images, directories = files.supported(["a", "b"])
    assert images == ["a", "b"]
    assert not directories


def test_tar_gz_not_an_image(tmpdir):
    """Test if is_image for a tar.gz returns False.

    The default implementation of QImageReader.canRead returns True which is not
    correct.
    """
    outfile = str(tmpdir.join("dummy.tar.gz"))
    indirectory = str(tmpdir.mkdir("indir"))
    with tarfile.open(outfile, mode="w:gz") as tar:
        tar.add(indirectory, arcname=os.path.basename(indirectory))
    assert files.is_image(outfile) is False


def test_sizeof_fmt():
    assert files.sizeof_fmt(2048) == "2.0K"


def test_sizeof_fmt_small_file():
    assert files.sizeof_fmt(510) == "510B"


def test_get_size_directory_with_directories(mocker):
    paths = [str(i) for i in range(15)]
    mocker.patch("os.listdir", return_value=paths)
    mocker.patch("os.path.isdir", return_value=True)
    mocker.patch("os.path.isfile", return_value=False)
    assert files.get_size_directory("any") == "15"


def test_get_size_directory_with_images(mocker):
    paths = [str(i) for i in range(10)]
    mocker.patch("os.listdir", return_value=paths)
    mocker.patch("os.path.isdir", return_value=False)
    mocker.patch.object(files, "is_image", return_value=True)
    assert files.get_size_directory("any") == "10"


def test_get_size_with_permission_error(mocker):
    mocker.patch("os.path.isfile", side_effect=PermissionError)
    assert files.get_size("any") == "N/A"
