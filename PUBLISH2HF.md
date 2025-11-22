# Publishing LDData to Hugging Face (upload.py)

This document summarizes how to use `upload.py` to publish the `LDData` repository to the Hugging Face Datasets Hub, and provides notes for CI and secure authentication.

## Requirements

- Python 3.8+
- `huggingface_hub>=0.32.0` (install with `pip install "huggingface_hub>=0.32.0"`)
- Network access to `huggingface.co` when uploading

## Basic usage

Run from the repository root (or pass `--local-path`):

```bash
python upload.py \
  --repo-id QMCSoftware/LDData \
  --local-path .
```

This will create (or reuse) the dataset repo `QMCSoftware/LDData` on the Hub and upload files from the local checkout.

## Important flags

- `--repo-id`: target HF dataset id (default: `QMCSoftware/LDData`).
- `--local-path`: path to local LDData checkout (default: `.`).
- `--token`: HF token. If omitted, the script reads the `HF_TOKEN` environment variable.
- `--private`: create the dataset as private.
- `--dry-run`: don't upload; print what would be done.
- `--reset-remote`: delete the remote dataset repo on the Hub before uploading (destructive).
- `--yes`: skip interactive confirmation prompts (use with care, required for non-interactive CI with `--reset-remote`).

Example (non-interactive destructive reset + upload):

```bash
export HF_TOKEN="hf_xxx..."
python upload.py --repo-id QMCSoftware/LDData --local-path . --reset-remote --yes
```

## CI integration (GitHub Actions)

Create a repository secret named `HF_TOKEN` containing a Hugging Face token with the required permissions. Example workflow step:

```yaml
- name: Upload to HuggingFace
  env:
    HF_TOKEN: ${{ secrets.HF_TOKEN }}
  run: |
    python upload.py \
      --repo-id QMCSoftware/LDData \
      --local-path . \
      --reset-remote \
      --yes
```

Note: the repository included a workflow `.github/workflows/sync-to-huggingface.yml` that already calls `upload.py` for automated syncs. If you want to avoid destructive resets in CI, remove `--reset-remote --yes` from the workflow.

## Local development (recommended)

This repository includes an `env.yml` Conda environment for reproducible local development and for CI. Use it to create and activate the `lddata` environment, then install the package in editable mode:

```bash
conda env create -f env.yml
conda activate lddata
python -m pip install --upgrade pip
python -m pip install -e .
```

Notes:
- CI uses `env.yml` (via `conda-incubator/setup-miniconda`) so the same environment is reproducible in GitHub Actions.
- `pip install -e .` uses the project's packaging (see `pyproject.toml`) so tests can import the `LDData` package.

## Packaging (pyproject.toml)

This repo uses a PEP 621 `pyproject.toml` with setuptools as the build backend. That lets `pip install -e .` (editable install) work consistently in both local and CI environments.

If you prefer modern packaging workflows, keep `pyproject.toml` and use `pip` inside the conda env as shown above.

## Run tests

Unit tests are designed to be hermetic (they mock network calls). Integration tests that exercise the real Hugging Face API are gated and skipped by default.

Run the full unit test suite:

```bash
pytest -q
```

Run the destructive integration test (WARNING: deletes remote dataset)

```bash
export HF_TOKEN=hf_xxx...   # token with write/delete perms
export HF_INTEGRATION=1
pytest -q tests/test_integration_hf.py
```

The integration test is intentionally skipped unless you set `HF_INTEGRATION=1` and provide `HF_TOKEN`. This prevents accidental destructive runs in CI or by contributors.

## Quick checklist before publishing

- Ensure `HF_TOKEN` (or SSH deploy key) is available and has write/delete permissions for the target dataset.
- Verify `upload.py` flags: use `--dry-run` to preview, and use `--reset-remote --yes` only when you intend to wipe the remote repo.
- Prefer SSH deploy keys for persistent automation where possible.


## Authentication & security

Preferred options (ordered):

1. **SSH deploy key** (recommended for long-lived automation)
   - On Hugging Face dataset repo settings, add a *deploy key* with write access.
   - Use the SSH clone URL `git@huggingface.co:datasets/ORG/REPO.git` in scripts or CI.
   - Benefits: no tokens in environment, standard SSH key management.

2. **CI secrets + `GIT_ASKPASS`** (used by `scripts/git_lfs_upload.sh`)
   - Inject token into CI via secrets (e.g. `HF_TOKEN`) and use a temporary non-disclosable `GIT_ASKPASS` helper so the token is not visible in process listings.
   - The repository's `scripts/git_lfs_upload.sh` uses this method to avoid embedding the token in the URL.

3. **HF_TOKEN environment variable** passed directly to `upload.py`
   - `upload.py` reads `HF_TOKEN` from the environment if `--token` is not provided.
   - This is acceptable for CI (secrets are injected into the runner), but avoid printing the token or embedding it in command lines.

Avoid embedding tokens in clone URLs (e.g. `https://hf_xxx@...`) because they appear in `ps` output, shell history and logs.

## Safety notes about `--reset-remote`

- `--reset-remote` deletes the remote dataset repository (destructive). Use `--yes` to skip confirmation in automation.
- If deletion fails (insufficient permissions or other errors), the script currently logs a warning and continues to (re)create the repo — change this behavior if you want strict failure.

## Troubleshooting

- If you see `ModuleNotFoundError: No module named 'huggingface_hub'`, install the dependency in the environment running the script: `pip install huggingface_hub`.
- For intermittent upload errors, the script uses retries and exponential backoff; ensure you have stable network connectivity.

## Examples

- Dry run to see what would happen:
  ```bash
  python upload.py --local-path . --dry-run
  ```

- Upload privately without prompting:
  ```bash
  python upload.py --repo-id MyOrg/MyDataset --private --yes
  ```

## Related scripts

- `scripts/git_lfs_upload.sh` — alternate upload method that uses git + git-lfs and commits/pushes selected folders; supports `GIT_ASKPASS` when `HF_TOKEN` is set.
- `.github/workflows/sync-to-huggingface.yml` — example workflow that syncs selected paths to Hugging Face using `upload.py`.
- `.github/workflows/ci.yml` — main CI workflow that runs tests; does not upload by default.