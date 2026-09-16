import re
import shutil
import subprocess
from pathlib import Path

import pytest


def _scripts(source: str):
    return re.findall(r"<script(?:[^>]*)>(.*?)</script>", source, re.S | re.I)


def test_dashboard_javascript_syntax():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed")

    root = Path(__file__).resolve().parents[1]
    template = (root / "dashboard_ui" / "templates.py").read_text()
    runtime = (root / "dashboard_ui" / "runtime_fix.py").read_text()
    scripts = _scripts(template) + _scripts(runtime)
    assert scripts, "No dashboard JavaScript blocks found"

    for index, script in enumerate(scripts):
        result = subprocess.run(
            [node, "--check", "-"],
            input=script,
            text=True,
            capture_output=True,
        )
        assert result.returncode == 0, f"Dashboard script {index} failed: {result.stderr}"
