import importlib.util
import shutil
import subprocess

import pytest
from indexkit.data import ROOT


def test_java_matches_python(tmp_path):
    if not shutil.which("javac") or not shutil.which("java"):
        pytest.skip("Optional Java compiler/runtime unavailable; do not claim Java verification")
    script = ROOT / "java_bs/generate_reference.py"
    spec = importlib.util.spec_from_file_location("java_reference", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    reference = tmp_path / "reference.csv"
    module.generate(reference)
    subprocess.run(
        ["javac", "-d", str(tmp_path), str(ROOT / "java_bs/BlackScholes.java")],
        check=True,
        capture_output=True,
        text=True,
    )
    result = subprocess.run(
        ["java", "-cp", str(tmp_path), "BlackScholes", str(reference)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "passed: 5" in result.stdout
