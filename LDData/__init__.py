"""LDData package shim.

This package file exposes the top-level `upload.py` module as
`LDData.upload` so tests and imports using `from LDData import upload`
work without moving the original script.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


def _load_top_level_module(name: str, filename: Path):
    spec = importlib.util.spec_from_file_location(name, str(filename))
    module = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(module)
    return module


# Locate the repository root (parent of this package directory)
_repo_root = Path(__file__).resolve().parent.parent
# Path to the existing top-level upload.py
_upload_path = _repo_root / "upload.py"

if _upload_path.exists():
    # Load the top-level upload.py as a module named 'LDData.upload'
    _mod = _load_top_level_module("LDData.upload", _upload_path)
    # Expose it in the package namespace
    upload = _mod
    __all__ = ["upload"]
else:
    # Fallback: create a minimal stub so imports fail with clearer message later
    def _missing():
        raise ImportError("upload.py not found at project root")

    upload = _missing
    __all__ = ["upload"]
