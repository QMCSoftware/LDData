import os
import shutil
import tempfile
from pathlib import Path

import pytest

try:
    from huggingface_hub import HfApi
except Exception:  # pragma: no cover - if huggingface_hub missing, skip integration
    HfApi = None


HF_INTEGRATION = os.environ.get("HF_INTEGRATION", "0").lower() in ("1", "true", "yes")
HF_TOKEN = os.environ.get("HF_TOKEN")
REPO_ID = os.environ.get("HF_INTEGRATION_REPO", "QMCSoftware/LDData")


@pytest.mark.skipif(not HF_INTEGRATION or HfApi is None, reason="Integration test disabled (set HF_INTEGRATION=1 and install huggingface_hub)")
def test_delete_and_upload_lattice_and_readme():
    """Integration test: delete remote dataset repo and upload only `lattice/` + `README.md`.

    WARNING: This test is destructive. It will delete the remote dataset repo
    specified by `REPO_ID` and recreate it. Only enable it locally or in CI
    when you explicitly want this behavior by setting `HF_INTEGRATION=1`.
    """

    if not HF_TOKEN:
        pytest.skip("HF_TOKEN not provided; skipping destructive integration test")

    repo_root = Path(__file__).resolve().parents[2]
    src_lattice = repo_root / "lattice"
    src_readme = repo_root / "README.md"

    if not src_lattice.exists():
        pytest.skip("lattice/ folder not present in repo root; skipping")

    api = HfApi(token=HF_TOKEN)

    # Delete remote repo if it exists
    try:
        api.delete_repo(repo_id=REPO_ID, repo_type="dataset")
    except Exception:
        # ignore errors (repo may not exist or insufficient perms)
        pass

    # Create the dataset repo (exist_ok=True will not fail if already present)
    try:
        api.create_repo(repo_id=REPO_ID, repo_type="dataset", exist_ok=True)
    except Exception as exc:
        pytest.fail(f"Failed to create dataset repo {REPO_ID}: {exc}")

    # Prepare a temporary folder containing only lattice/ and README.md
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        shutil.copytree(src_lattice, td_path / "lattice")
        if src_readme.exists():
            shutil.copy(src_readme, td_path / "README.md")

        # Upload the folder contents to the dataset repo
        try:
            api.upload_folder(folder_path=str(td_path), repo_id=REPO_ID, repo_type="dataset")
        except TypeError:
            # Some versions of HfApi.upload_folder have a different signature
            api.upload_folder(str(td_path), repo_id=REPO_ID, repo_type="dataset")

    # Verify that README.md exists in the remote dataset files
    files = api.list_repo_files(REPO_ID, repo_type="dataset")
    lowered = [f.lower() for f in files]
    assert any(p.endswith("readme.md") for p in lowered), "README.md not found in uploaded dataset"
