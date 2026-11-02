"""Syntax-check only the new dashboard script without a browser or file writes."""
from pathlib import Path
import re
import subprocess


root = Path(__file__).resolve().parent.parent
html = (root / "module/web/index.html").read_text()
scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
if len(scripts) != 1:
    raise SystemExit("Expected one local dashboard script")
subprocess.run(["node", "--check"], input=scripts[0], text=True, check=True)
print("Dashboard JavaScript syntax passed")
