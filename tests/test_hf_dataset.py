from huggingface_hub import HfApi


def test_sou_cheng_lddata_exist_and_has_readme():
    """Fast smoke test: ensure the public dataset repo exists and includes a README."""
    api = HfApi()
    files = api.list_repo_files("Sou-Cheng/LDData", repo_type="dataset")

    assert isinstance(files, list), "Expected list of files from Hugging Face"
    assert len(files) > 0, "Dataset 'Sou-Cheng/LDData' appears to be empty or not accessible"

    # Check for README presence in a case-insensitive manner
    lowered = [f.lower() for f in files]
    assert any(name.endswith("readme.md") for name in lowered), (
        "Expected a README.md in the dataset files; got: " + ", ".join(files[:10])
    )
