import tempfile
import os
from pathlib import Path
import types

import pytest

from LDData import upload as up


class DummyAPI:
    def __init__(self):
        self.deleted = False
        self.created = False
        self.uploaded_folder = False
        self.uploaded_large = False
        self.uploaded_files = []

    def delete_repo(self, **kwargs):
        self.deleted = True

    def create_repo(self, **kwargs):
        self.created = True

    def upload_folder(self, *args, **kwargs):
        self.uploaded_folder = True

    def upload_large_folder(self, *args, **kwargs):
        self.uploaded_large = True

    def upload_file(self, *args, **kwargs):
        # record path_in_repo argument if present
        if 'path_in_repo' in kwargs:
            self.uploaded_files.append(kwargs['path_in_repo'])
        else:
            # some API variants use positional args; accept that case too
            if len(args) >= 2:
                self.uploaded_files.append(args[1])


def test_delete_remote_repo_calls_delete_when_yes_true():
    api = DummyAPI()
    # call with yes=True to avoid interactive prompt
    up.delete_remote_repo(api, repo_id="owner/repo", token="tok", yes=True)
    assert api.deleted is True


def test_perform_bulk_upload_uses_upload_folder(tmp_path, monkeypatch):
    api = DummyAPI()
    # create a small file so total_size < LARGE_THRESHOLD
    d = tmp_path / "repo"
    d.mkdir()
    f = d / "a.txt"
    f.write_text("hello")

    ok = up.perform_bulk_upload(api, local_path=d, repo_id="owner/repo", ignore_patterns=[], token="tok")
    assert ok is True
    assert api.uploaded_folder is True


def test_perform_bulk_upload_large_prefers_large_when_available(tmp_path):
    api = DummyAPI()
    # create a file > LARGE_THRESHOLD to trigger large upload path
    d = tmp_path / "repo2"
    d.mkdir()
    big = d / "big.bin"
    # write a file slightly larger than threshold (50 MiB)
    big.write_bytes(b"0" * (50 * 1024 * 1024 + 10))

    # monkeypatch attribute to simulate large upload existing
    # DummyAPI already has upload_large_folder method
    ok = up.perform_bulk_upload(api, local_path=d, repo_id="owner/repo", ignore_patterns=[], token="tok")
    assert ok is True
    assert api.uploaded_large is True


def test_perform_per_file_upload_calls_upload_file(tmp_path):
    api = DummyAPI()
    # create a couple of files list format expected by perform_per_file_upload: (fullpath, rel)
    d = tmp_path / "repo3"
    d.mkdir()
    (d / "x.txt").write_text("x")
    (d / "sub").mkdir()
    (d / "sub" / "y.txt").write_text("y")

    files = []
    for root, _, fnames in os.walk(d):
        for fn in fnames:
            full = Path(root) / fn
            rel = os.path.relpath(str(full), start=str(d)).replace(os.sep, '/')
            files.append((full, rel))

    up.perform_per_file_upload(api, files, repo_id="owner/repo", token="tok")
    # uploaded_files should include both relative paths
    assert any(p.endswith('x.txt') for p in api.uploaded_files)
    assert any(p.endswith('sub/y.txt') for p in api.uploaded_files)
