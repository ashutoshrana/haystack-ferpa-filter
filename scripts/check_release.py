"""Validate source version, release tag, and built wheel metadata; no network."""

import ast
import sys
import re
import zipfile
import tarfile
from email.parser import BytesParser
from pathlib import Path

root = Path(__file__).resolve().parents[1]
license_text = (root / "LICENSE").read_bytes()
assert b"END OF TERMS AND CONDITIONS" in license_text, "Complete Apache license text required"
project_text = (root / "pyproject.toml").read_text()
project = {
    key: ast.literal_eval(match.group(1))
    for key in ("name", "version")
    if (match := re.search(r"^" + key + r"\s*=\s*(\"[^\"]*\")", project_text, re.MULTILINE))
}
runtime = root / "src/haystack_integrations/components/filters/ferpa_filter/__about__.py"
version = next(
    ast.literal_eval(node.value)
    for node in ast.parse(runtime.read_text()).body
    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__version__" for t in node.targets)
)
assert project.get("version", version) == version, "Source versions disagree"
if len(sys.argv) > 1:
    assert sys.argv[1] == "v" + version, "Release tag must match source version"
for wheel in (root / "dist").glob("*.whl"):
    with zipfile.ZipFile(wheel) as archive:
        metadata = BytesParser().parsebytes(
            archive.read(next(n for n in archive.namelist() if n.endswith(".dist-info/METADATA")))
        )
        assert metadata["Version"] == version, "Wheel version mismatch"
        assert metadata["Name"].replace("_", "-") == project["name"], "Wheel distribution mismatch"
        assert str(runtime.relative_to(root / "src")) in archive.namelist(), "Runtime module absent"
        licenses = [n for n in archive.namelist() if n.endswith("/LICENSE")]
        assert licenses and all(archive.read(n) == license_text for n in licenses), "Wheel license missing or changed"
for sdist in (root / "dist").glob("*.tar.gz"):
    with tarfile.open(sdist) as archive:
        licenses = [m for m in archive.getmembers() if m.name.endswith("/LICENSE") and m.isfile()]
        assert licenses and all(archive.extractfile(m).read() == license_text for m in licenses), "Source license missing or changed"
print(version)
