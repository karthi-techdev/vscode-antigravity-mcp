import os
import tempfile
import pytest
from client.executor import LocalIDEExecutor


def test_powershell_execution():
    with tempfile.TemporaryDirectory() as temp_dir:
        executor = LocalIDEExecutor(workspace_dir=temp_dir)
        res = executor.run_powershell("Write-Output 'Hello PowerShell'")
        assert res["shell"] == "powershell"
        assert res["exit_code"] == 0
        assert "Hello PowerShell" in res["stdout"]


def test_cmd_execution():
    with tempfile.TemporaryDirectory() as temp_dir:
        executor = LocalIDEExecutor(workspace_dir=temp_dir)
        res = executor.run_cmd("echo Hello CMD")
        assert res["shell"] == "cmd"
        assert res["exit_code"] == 0
        assert "Hello CMD" in res["stdout"]


def test_git_execution():
    with tempfile.TemporaryDirectory() as temp_dir:
        executor = LocalIDEExecutor(workspace_dir=temp_dir)
        # Initialize a test git repo
        init_res = executor.run_git("init")
        assert init_res["exit_code"] == 0

        # Check status
        status_res = executor.run_git("status")
        assert status_res["exit_code"] == 0
        assert ("On branch" in status_res["stdout"] or "No commits yet" in status_res["stdout"])


def test_defender_alert_handling():
    with tempfile.TemporaryDirectory() as temp_dir:
        executor = LocalIDEExecutor(workspace_dir=temp_dir)
        # Run a simulated command that exits with error containing 'virus or potentially unwanted software'
        res = executor.run_powershell("[Console]::Error.WriteLine('Operation did not complete successfully because the file contains a virus or potentially unwanted software.'); exit 1")
        assert res["exit_code"] != 0
        assert "Windows Security Alert" in res["stderr"]
        assert "python bridge.py --allow-defender" in res["stderr"]
