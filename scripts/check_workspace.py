"""Dependency-free source, version and whitespace check; does not contact USB."""
from pathlib import Path
import re


root = Path(__file__).resolve().parent.parent
version = (root / "VERSION").read_text().strip()
if not re.fullmatch(r"\d+\.\d+\.\d+", version):
    raise SystemExit("VERSION must be a semantic version without a tag prefix")
checked = 0
for directory in ("cellforge", "scripts", "tests"):
    for path in sorted((root / directory).rglob("*.py")):
        compile(path.read_text(), str(path), "exec")
        checked += 1
for path in [root / "Makefile", root / "VERSION", root / "README.md",
             *sorted((root / "docs").glob("*.md")),
             *sorted((root / "cellforge").glob("*.py")),
             *sorted((root / "scripts").glob("*.py")),
             *sorted((root / "tests").glob("*.py"))]:
    for number, line in enumerate(path.read_text().splitlines(), 1):
        if line.rstrip() != line:
            raise SystemExit("Trailing whitespace: %s:%d" % (path.relative_to(root), number))
print("Cellforge %s: %d Python sources compiled; whitespace checked" % (version, checked))
