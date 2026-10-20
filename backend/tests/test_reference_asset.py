"""The checked-in Chatterbox reference voice and its rebuild script."""
import hashlib
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
VOICES = ROOT / "assets" / "voices"
REFERENCE_MD5 = "84d201496b4ba6601583dec45e1ee29c"


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def _load_build_reference():
    spec = importlib.util.spec_from_file_location("build_reference", ROOT / "scripts" / "build_reference.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_checked_in_reference_matches_its_recorded_md5():
    assert _md5(VOICES / "ref_p241_clean.wav") == REFERENCE_MD5


def test_stylize_reproduces_the_checked_in_reference(tmp_path):
    pytest.importorskip("parselmouth")
    out = tmp_path / "ref.wav"

    _load_build_reference().stylize(str(VOICES / "p241_vits_source.wav"), str(out))

    assert _md5(out) == REFERENCE_MD5


def test_attribution_names_vctk_licence():
    readme = (VOICES / "README.md").read_text()

    assert "VCTK" in readme
    assert "CC BY 4.0" in readme
