import os
import tempfile
import pytest
from client.executor import LocalIDEExecutor


def test_executor_file_lifecycle():
    with tempfile.TemporaryDirectory() as temp_dir:
        executor = LocalIDEExecutor(workspace_dir=temp_dir)

        # 1. Write file
        write_res = executor.write_file("hello.txt", "line 1\nline 2\nline 3\n")
        assert write_res["status"] == "success"

        # 2. Read file
        read_res = executor.read_file("hello.txt")
        assert read_res["total_lines"] == 3
        assert "line 1" in read_res["content"]

        # 3. Edit file
        edit_res = executor.edit_file("hello.txt", "line 2", "line two modified")
        assert edit_res["status"] == "success"
        assert edit_res["replacements_made"] == 1

        # Verify edited content
        verify_res = executor.read_file("hello.txt")
        assert "line two modified" in verify_res["content"]

        # 4. List directory
        list_res = executor.list_directory(".")
        assert any(e["name"] == "hello.txt" for e in list_res["entries"])

        # 5. Search files
        search_res = executor.search_files("modified")
        assert search_res["matches_found"] == 1
        assert "hello.txt" in search_res["matches"][0]["file"]


def test_executor_path_traversal_prevention():
    with tempfile.TemporaryDirectory() as temp_dir:
        executor = LocalIDEExecutor(workspace_dir=temp_dir)
        # Attempt path traversal
        with pytest.raises(PermissionError):
            executor.read_file("../../../secret.txt")
