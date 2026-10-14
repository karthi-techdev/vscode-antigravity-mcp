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


def test_executor_new_file_management_tools():
    with tempfile.TemporaryDirectory() as temp_dir:
        executor = LocalIDEExecutor(workspace_dir=temp_dir)

        # 1. Create directory
        dir_res = executor.create_directory("nested/subfolder")
        assert dir_res["status"] == "success"
        assert os.path.isdir(os.path.join(temp_dir, "nested", "subfolder"))

        # 2. Write file inside directory
        executor.write_file("nested/subfolder/test.py", "print('hello')\nprint('world')\n")

        # 3. Get file info
        info_res = executor.get_file_info("nested/subfolder/test.py")
        assert info_res["exists"] is True
        assert info_res["type"] == "file"
        assert info_res["line_count"] == 2
        assert info_res["extension"] == ".py"
        assert info_res["size_bytes"] > 0

        # Check non-existent file info
        missing_res = executor.get_file_info("does_not_exist.txt")
        assert missing_res["exists"] is False

        # 4. Move / Rename file
        move_res = executor.move_or_rename_file(
            "nested/subfolder/test.py",
            "nested/renamed.py"
        )
        assert move_res["status"] == "success"
        assert not os.path.exists(os.path.join(temp_dir, "nested", "subfolder", "test.py"))
        assert os.path.exists(os.path.join(temp_dir, "nested", "renamed.py"))

        # 5. Delete file
        del_file_res = executor.delete_file("nested/renamed.py")
        assert del_file_res["status"] == "success"
        assert del_file_res["type"] == "file"
        assert not os.path.exists(os.path.join(temp_dir, "nested", "renamed.py"))

        # 6. Delete directory recursively
        del_dir_res = executor.delete_file("nested", recursive=True)
        assert del_dir_res["status"] == "success"
        assert del_dir_res["type"] == "directory"
        assert not os.path.exists(os.path.join(temp_dir, "nested"))

        # 7. Boundary protection: Cannot delete project root
        with pytest.raises(PermissionError):
            executor.delete_file(".")

