"""Tests for file system operations."""

import os
from pathlib import Path
import pytest
from campuscli.tools.file_ops import (
    list_directory,
    read_file,
    replace_in_file,
    search_files,
    write_file,
)


def test_write_and_read_file(tmp_path: Path):
    test_file = tmp_path / "hello.py"
    content = "def greet():\n    return 'hello world'\n"

    res_write = write_file(str(test_file), content)
    assert "Successfully wrote" in res_write

    res_read = read_file(str(test_file))
    assert "def greet():" in res_read
    assert "1 |" in res_read


def test_replace_in_file(tmp_path: Path):
    test_file = tmp_path / "app.py"
    initial_content = "def calculate():\n    x = 10\n    return x\n"
    write_file(str(test_file), initial_content)

    res_replace = replace_in_file(
        str(test_file),
        target_content="    x = 10",
        replacement_content="    x = 20"
    )
    assert "Successfully replaced" in res_replace

    res_read = read_file(str(test_file))
    assert "x = 20" in res_read
    assert "x = 10" not in res_read


def test_list_and_search_files(tmp_path: Path):
    (tmp_path / "subdir").mkdir()
    write_file(str(tmp_path / "file1.txt"), "CampusCLI open source model test")
    write_file(str(tmp_path / "subdir" / "file2.txt"), "another piece of text")

    list_res = list_directory(str(tmp_path), recursive=True)
    assert "file1.txt" in list_res
    assert "subdir" in list_res

    search_res = search_files(query="CampusCLI", dir_path=str(tmp_path))
    assert "file1.txt" in search_res
