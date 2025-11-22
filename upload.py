#!/usr/bin/env python
"""
upload.py

Upload the QMCSoftware/LDData repository (low discrepancy generating vectors
and matrices) to the Hugging Face Datasets Hub as a dataset repo.

This script:

1. Creates (or reuses) a dataset repo on the Hub.
2. Uploads all files from a local LDData checkout using `upload_folder`.
3. Leaves README.md in place so it becomes the dataset card.
   After upload you can edit the card in the web UI to:
     - Link to the paper (arXiv:2502.14256).
     - Add "Citation" and "Uses" sections, similar to
       - facebook/omnilingual-asr-corpus
       - nvidia/PhysicalAI-Autonomous-Vehicles
       - moondream/refcoco-m

Requirements:
    pip install "huggingface_hub>=0.32.0"

Authentication:
    - Either set HF_TOKEN in your environment:
        export HF_TOKEN=hf_xxx...
      OR pass --token on the command line.

Example usage:
    python upload.py \
        --repo-id QMCSoftware/LDData \
        --local-path /path/to/local/LDData

After upload you’ll be able to do, e.g.:

    from datasets import load_dataset
    ds = load_dataset("QMCSoftware/LDData")

and link the dataset to your paper page on Hugging Face.
"""

import argparse
import os
import sys
import time
import random
from pathlib import Path
import httpx
import fnmatch

from huggingface_hub import HfApi, create_repo  # type: ignore
from huggingface_hub.errors import HfHubHTTPError  # type: ignore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload LDData to the Hugging Face Datasets Hub."
    )
    parser.add_argument(
        "--repo-id",
        type=str,
        default="QMCSoftware/LDData",
        help="Target dataset repo id on the Hub (e.g. 'QMCSoftware/LDData').",
    )
    parser.add_argument(
        "--local-path",
        type=str,
        default=".",
        help="Path to local LDData checkout (default: current directory).",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=None,
        help="Hugging Face access token. If omitted, HF_TOKEN env var is used.",
    )
    parser.add_argument(
        "--private",
        action="store_true",
        help="Create the dataset repo as private (default: public).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not upload, just print what would be done.",
    )
    parser.add_argument(
        "--reset-remote",
        action="store_true",
        help="Delete the remote dataset repo on the Hub before uploading (destructive).",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Answer yes to any interactive confirmation prompts (use with care).",
    )
    return parser.parse_args()


def get_token(cmd_token: str | None) -> str:
    token = cmd_token or os.environ.get("HF_TOKEN")
    if not token:
        raise SystemExit(
            "No token provided. Please either:\n"
            "  - set HF_TOKEN in your environment, or\n"
            "  - pass --token hf_xxx... on the command line."
        )
    return token


def retry_call(
    fn,
    *args,
    retries: int = 6,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    allowed_status_for_retry=(429, 500, 502, 503, 504),
    **kwargs,
):
    """
    Call `fn(*args, **kwargs)` with retries on rate limit (429), server errors and read timeouts.
    Uses exponential backoff with jitter. If the server provides a Retry-After header it will be honored.
    """
    last_exc = None
    for attempt in range(retries):
        try:
            return fn(*args, **kwargs)
        except HfHubHTTPError as exc:
            last_exc = exc
            # Try to extract status code and headers robustly
            status_code = getattr(exc, "status_code", None)
            headers = {}
            resp = getattr(exc, "response", None)
            if resp is not None:
                try:
                    status_code = getattr(resp, "status_code", status_code)
                    headers = getattr(resp, "headers", {}) or {}
                except Exception as exc:
                    # Log the exception for debugging purposes but continue execution
                    print(f"WARNING: An unexpected error occurred: {exc!r}")
            if status_code in allowed_status_for_retry:
                # Honor Retry-After if present
                retry_after = None
                for key in ("retry-after", "Retry-After"):
                    if key in headers:
                        retry_after = headers.get(key)
                        break
                if retry_after is not None:
                    try:
                        delay = int(retry_after)
                    except Exception:
                        try:
                            delay = float(retry_after)
                        except Exception:
                            delay = None
                else:
                    delay = min(max_delay, base_delay * (2 ** attempt))
                    delay += random.uniform(0, base_delay)
                # On last attempt, break and raise
                if attempt == retries - 1:
                    break
                time.sleep(delay)
                continue
            # Non-retryable HTTP error
            raise
        except httpx.ReadTimeout as exc:
            last_exc = exc
            if attempt == retries - 1:
                break
            delay = min(max_delay, base_delay * (2 ** attempt)) + random.uniform(0, base_delay)
            time.sleep(delay)
            continue
        except Exception as exc:
            # For other exceptions, do not retry except maybe transient httpx.NetworkError -- keep simple and re-raise
            last_exc = exc
            raise
    # If we exit loop without returning, raise last exception
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("retry_call failed without exception")


def create_api(token: str) -> HfApi:
    """Create an authenticated HfApi client."""
    return HfApi(token=token)


def delete_remote_repo(api: HfApi, repo_id: str, token: str, yes: bool) -> None:
    """Delete the remote dataset repo if requested. Non-fatal on errors."""
    if not yes:
        resp = input(
            f"Are you sure you want to DELETE the dataset repo '{repo_id}' on Hugging Face? This is irreversible. Type 'yes' to continue: "
        )
        if resp.strip().lower() != "yes":
            print("Aborting: remote reset cancelled by user.")
            sys.exit(0)

    print(f"Deleting remote dataset repo '{repo_id}' (if it exists) on Hugging Face...")
    try:
        retry_call(getattr(api, "delete_repo"), repo_id=repo_id, repo_type="dataset", token=token)
        print("Remote dataset repo deleted (or did not exist).")
    except HfHubHTTPError as exc:
        print()
        print("WARNING: Failed to delete remote dataset repo:")
        print(f"  {exc!r}")
        print("Continuing to (re)create the repository.")
    except Exception as exc:
        print()
        print("WARNING: Unexpected error while attempting to delete remote repo:")
        print(f"  {exc!r}")
        print("Continuing to (re)create the repository.")


def create_or_reuse_repo(repo_id: str, private: bool, token: str) -> None:
    """Create (or reuse) the dataset repo on the Hub."""
    print(f"Creating (or reusing) dataset repo '{repo_id}' on the Hub...")
    retry_call(create_repo, repo_id=repo_id, repo_type="dataset", private=private, exist_ok=True, token=token)


def build_ignore_checker(ignore_patterns):
    def is_ignored(rel_path: str) -> bool:
        for patt in ignore_patterns:
            if fnmatch.fnmatch(rel_path, patt) or fnmatch.fnmatch("/" + rel_path, patt):
                return True
        return False

    return is_ignored


def gather_files(local_path: Path, ignore_patterns):
    """Return a list of (full_path, rel_posix_path) and total size, skipping ignore patterns."""
    is_ignored = build_ignore_checker(ignore_patterns)
    files_to_upload = []
    total_size = 0
    for root, _, files in os.walk(local_path):
        for fname in files:
            full = Path(root) / fname
            rel = os.path.relpath(str(full), start=str(local_path))
            rel = rel.replace(os.sep, "/")
            if rel.startswith("./"):
                rel = rel[2:]
            if rel.startswith("/"):
                rel = rel.lstrip("/")
            if is_ignored(rel):
                continue
            try:
                sz = full.stat().st_size
            except OSError:
                sz = 0
            files_to_upload.append((full, rel))
            total_size += sz
    return files_to_upload, total_size


def perform_bulk_upload(api: HfApi, local_path: Path, repo_id: str, ignore_patterns, token: str) -> bool:
    """Attempt bulk upload via upload_large_folder or upload_folder. Returns True on success."""
    LARGE_THRESHOLD = 50 * 1024 * 1024
    # prefer upload_large_folder if folder is large and API provides it
    files_to_upload, total_size = gather_files(local_path, ignore_patterns)
    try:
        if total_size > LARGE_THRESHOLD and hasattr(api, "upload_large_folder"):
            try:
                retry_call(getattr(api, "upload_large_folder"), folder_path=str(local_path), repo_id=repo_id, repo_type="dataset", ignore_patterns=ignore_patterns, token=token)
                return True
            except TypeError:
                retry_call(getattr(api, "upload_large_folder"), folder_path=str(local_path), repo_id=repo_id, repo_type="dataset", token=token)
                return True
            except Exception as exc:
                print()
                print("ERROR: upload_large_folder failed:")
                print(f"  {exc!r}")
                print("Falling back to per-file upload...")
                return False
        else:
            retry_call(getattr(api, "upload_folder"), folder_path=str(local_path), repo_id=repo_id, repo_type="dataset", ignore_patterns=ignore_patterns)
            return True
    except httpx.ReadTimeout:
        print()
        print("ERROR: Upload read timed out.")
        print("Possible actions:")
        print("  - Check your network connection and try again.")
        print("  - Try uploading in smaller batches (split large files or directories).")
        print("  - Use `HfApi().upload_large_folder(...)` or the CLI `hf upload-large-folder` if available.")
        print("  - Upgrade huggingface_hub to the latest version in case it adds improved timeout handling.")
        print("  - If you have very large files, consider using git-lfs or the web UI.")
        sys.exit(1)
    except TypeError as exc:
        print()
        print("ERROR: Upload function raised a TypeError (likely a signature mismatch):")
        print(f"  {exc!r}")
        print("Falling back to per-file upload...")
        return False
    except HfHubHTTPError as exc:
        print()
        print("ERROR: HF Hub returned an HTTP error while attempting to upload:")
        print(f"  {exc!r}")
        print("If this is a rate limit (429) you may need to wait, reduce request rate, or upgrade your plan.")
        sys.exit(1)
    except Exception:
        return False


def perform_per_file_upload(api: HfApi, files_to_upload, repo_id: str, token: str) -> None:
    """Upload files one-by-one as a fallback."""
    if not files_to_upload:
        return
    print("Falling back to per-file upload (this is slower but more robust for flaky networks)...")
    for idx, (file_path, rel) in enumerate(files_to_upload):
        path_in_repo = rel.lstrip("/")
        success = False
        try:
            retry_call(getattr(api, "upload_file"), path_or_fileobj=str(file_path), path_in_repo=path_in_repo, repo_id=repo_id, repo_type="dataset", token=token)
            success = True
        except httpx.ReadTimeout:
            print()
            print("ERROR: Per-file upload read timed out on:", path_in_repo)
            print("You can retry this script or use `hf upload-large-folder` / `HfApi.upload_large_folder`.")
            sys.exit(1)
        except HfHubHTTPError as exc:
            print()
            print("ERROR: Failed to upload file due to HF Hub HTTP error:", path_in_repo)
            print(f"  {exc!r}")
        except Exception as exc:
            print(f"WARNING: Failed to upload {path_in_repo!s}: {exc!r}")
        if not success:
            print(f"Failed to upload: {path_in_repo}")
        time.sleep(0.1 + random.uniform(0, 0.05))


def main() -> None:
    args = parse_args()

    local_path = Path(args.local_path).expanduser().resolve()
    if not local_path.exists():
        raise SystemExit(f"Local path does not exist: {local_path}")

    readme = local_path / "README.md"
    if not readme.exists():
        print(f"WARNING: {readme} does not exist. Are you sure this is the LDData repo root?", file=sys.stderr)

    token = get_token(args.token)
    repo_id = args.repo_id

    print(f"Using repo_id: {repo_id}")
    print(f"Local path : {local_path}")
    print(f"Private    : {args.private}")
    if args.dry_run:
        print("Dry run enabled: NOT creating or uploading, just showing intent.")
        return

    api = create_api(token)

    if args.reset_remote:
        delete_remote_repo(api, repo_id, token, args.yes)

    create_or_reuse_repo(repo_id, args.private, token)

    ignore_patterns = [
        "sc/*",
        ".git/*",
        ".gitignore",
        ".DS_Store",
        "__pycache__/*",
        "*.pyc",
        "*.pyo",
        "*~",
        "*.ipynb_checkpoints*",
        "raw.githubusercontent.com",
    ]

    print("Uploading local folder to the Hub (this may take a while)...")

    # gather files in case we need per-file fallback
    files_to_upload, _ = gather_files(local_path, ignore_patterns)

    bulk_ok = perform_bulk_upload(api, local_path, repo_id, ignore_patterns, token)
    if bulk_ok:
        print("Bulk upload succeeded — skipping per-file fallback.")
    else:
        perform_per_file_upload(api, files_to_upload, repo_id, token)

    dataset_url = f"https://huggingface.co/datasets/{repo_id}"
    print()
    print("✅ Upload complete.")
    print(f"Dataset is now available at: {dataset_url}")
    print()
    print("Next steps (recommended):")
    print("  1. Open the dataset page above in your browser.")
    print("  2. Edit the Dataset Card (README.md) to:")
    print("     - Add paper links (e.g., your QMCSoftware/LDData arXiv paper).")
    print("     - Add a 'Citations' section.")
    print("     - Add 'Uses' and 'Limitations' sections, similar to:")
    print("       - facebook/omnilingual-asr-corpus")
    print("       - nvidia/PhysicalAI-Autonomous-Vehicles")
    print("       - moondream/refcoco-m")
    print("  3. Use 'Paper' / 'Dataset' linking in the Hugging Face UI to")
    print("     attach the dataset to your paper so it shows up on the")
    print("     paper page and in discovery views.")


if __name__ == "__main__":
    main()