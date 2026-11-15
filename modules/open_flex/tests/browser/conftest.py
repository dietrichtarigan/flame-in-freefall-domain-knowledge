"""Shared browser-test setup: build the no-vendor variant once per session (needs the source PDF)."""
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="session", autouse=True)
def _build_test_variant():
    subprocess.run([sys.executable, "-I", os.path.join(ROOT, "tools", "build_app.py"), "--no-vendor",
                    "--out", os.path.join(ROOT, "dist", "test_no_vendor.html")], check=True)
