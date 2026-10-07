"""The README must only tell the reader to run make targets that exist."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _readme_targets() -> set[str]:
    text = (ROOT / "README.md").read_text()
    return set(re.findall(r"\bmake ([a-z][a-z0-9-]*)", text))


def _makefile_targets() -> set[str]:
    text = (ROOT / "Makefile").read_text()
    return set(re.findall(r"^([a-zA-Z][a-zA-Z0-9_-]*):", text, re.MULTILINE))


def test_readme_names_make_targets():
    assert {"setup-cuda", "check-cuda", "install-timer"} <= _readme_targets()


def test_every_readme_make_target_exists_in_makefile():
    missing = _readme_targets() - _makefile_targets()

    assert not missing, f"README names make targets missing from the Makefile: {sorted(missing)}"
