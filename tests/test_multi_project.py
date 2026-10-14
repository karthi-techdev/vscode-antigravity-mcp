import os
import tempfile
import pytest
from client.executor import LocalIDEExecutor


def test_multi_project_discovery_and_switching():
    with tempfile.TemporaryDirectory() as root_temp:
        # Create two sample projects inside the root directory
        proj_a = os.path.join(root_temp, "project-alpha")
        proj_b = os.path.join(root_temp, "project-beta")
        os.makedirs(proj_a)
        os.makedirs(proj_b)

        # Populate project-alpha (Python)
        with open(os.path.join(proj_a, "requirements.txt"), "w") as f:
            f.write("fastapi\n")
        with open(os.path.join(proj_a, "main.py"), "w") as f:
            f.write("print('Alpha')\n")

        # Populate project-beta (Node.js)
        with open(os.path.join(proj_b, "package.json"), "w") as f:
            f.write('{"name": "beta"}\n')
        with open(os.path.join(proj_b, "index.js"), "w") as f:
            f.write("console.log('Beta');\n")

        # Initialize executor with projects_root
        executor = LocalIDEExecutor(projects_root=root_temp)

        # 1. Discover projects
        discovery = executor.list_projects()
        assert discovery["total_projects"] == 2
        names = [p["name"] for p in discovery["projects"]]
        assert "project-alpha" in names
        assert "project-beta" in names

        # Check detected tech stack
        alpha_info = next(p for p in discovery["projects"] if p["name"] == "project-alpha")
        assert "Python" in alpha_info["type"]
        beta_info = next(p for p in discovery["projects"] if p["name"] == "project-beta")
        assert "Node.js" in beta_info["type"]

        # 2. Switch to project-alpha
        switch_res = executor.set_active_project("project-alpha")
        assert switch_res["status"] == "success"
        assert executor.active_project == "project-alpha"

        # Read file inside active project
        read_a = executor.read_file("main.py")
        assert "Alpha" in read_a["content"]

        # 3. Switch to project-beta
        executor.set_active_project("project-beta")
        assert executor.active_project == "project-beta"

        # Read file inside active project
        read_b = executor.read_file("index.js")
        assert "Beta" in read_b["content"]

        # 4. Target another project explicitly without switching active project
        read_explicit = executor.read_file("main.py", project="project-alpha")
        assert "Alpha" in read_explicit["content"]

        # 5. Execute command inside specific project
        cmd_res = executor.execute_command("echo HelloBeta", project="project-beta")
        assert cmd_res["exit_code"] == 0
        assert "HelloBeta" in cmd_res["stdout"]
