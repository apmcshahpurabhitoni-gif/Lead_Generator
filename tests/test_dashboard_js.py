import re
import shutil
import subprocess
from pathlib import Path
import pytest

def test_dashboard_javascript_syntax():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed")
    source = Path(__file__).resolve().parents[1] / "dashboard.py"
    script = re.search(r"<script>\n(.*?)\n</script>", source.read_text(), re.S)
    assert script
    result = subprocess.run([node, "--check", "-"], input=script.group(1), text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
