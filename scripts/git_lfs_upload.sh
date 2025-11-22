#!/usr/bin/env bash
# git_lfs_upload.sh
#
# Automate uploading folders/files to a Hugging Face dataset repo using git + git-lfs.
# This preserves folder structure, avoids API rate limits, and handles large files.
#
# Usage:
# 1) Make executable:
#    chmod +x scripts/git_lfs_upload.sh
# 2) Run:
#    ./scripts/git_lfs_upload.sh \
#      --repo-id QMCSoftware/LDData \
#      --local-path /Users/terrya/Documents/ProgramData/LDData \
#      --folders dnet,lattice,pregenerated_pointsets,README.md \
#      --branch main
#
# Environment notes:
# - If the repo is private, set HF_TOKEN in your environment or pass --token.
#   If HF_TOKEN is present, the script will embed it into the clone URL for non-interactive auth.
# - Install prerequisites: git, git-lfs, rsync (macOS: `brew install git-lfs rsync`).
# - The script commits and pushes each folder separately to reduce the size of each push.

set -euo pipefail
IFS=$'\n\t'

REPO_ID=""
LOCAL_PATH="."
FOLDERS=""
BRANCH="main"
HF_TOKEN="${HF_TOKEN:-}"
CLONE_DIR="hf_repo"
EXCLUDES=()
LFS_PATTERNS=("*.bin" "*.zip" "*.tar" "*.tgz" "*.h5" "*.npy" "*.npz" "*.ckpt" "*.pt" "*.pth" "*.gz")

print_usage() {
  cat <<EOF
Usage: $0 --repo-id ORG/Repo [options]

Options:
  --repo-id <org/repo>         Hugging Face dataset repo id (required)
  --local-path <path>          Local LDData root (default: .)
  --folders <comma-list>       Comma-separated folders/files to upload (e.g. dnet,lattice,README.md)
  --branch <branch>            Git branch to push to (default: main)
  --token <hf_token>           Hugging Face token (or set HF_TOKEN env var)
  --clone-dir <path>           Directory to clone the repo into (default: hf_repo)
  --exclude <pattern>          Add an rsync exclude pattern (can be supplied multiple times)
  -h, --help                   Show this help and exit

Example:
  $0 --repo-id QMCSoftware/LDData --local-path . --folders dnet,lattice,README.md

This script:
  - clones the target dataset repo,
  - copies the requested folders/files into the clone (preserving structure),
  - enables git-lfs for common large file types,
  - commits and pushes each folder/file separately to reduce push sizes.

EOF
}

# Simple arg parsing
while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-id)
      REPO_ID="$2"; shift 2;;
    --local-path)
      LOCAL_PATH="$2"; shift 2;;
    --folders)
      FOLDERS="$2"; shift 2;;
    --branch)
      BRANCH="$2"; shift 2;;
    --token)
      HF_TOKEN="$2"; shift 2;;
    --clone-dir)
      CLONE_DIR="$2"; shift 2;;
    --exclude)
      EXCLUDES+=("$2"); shift 2;;
    -h|--help)
      print_usage; exit 0;;
    *)
      echo "Unknown arg: $1" >&2; print_usage; exit 2;;
  esac
done

if [[ -z "$REPO_ID" ]]; then
  echo "--repo-id is required" >&2
  print_usage
  exit 2
fi

# Normalize LOCAL_PATH
LOCAL_PATH=$(cd "$LOCAL_PATH" && pwd)

echo "Repo ID: $REPO_ID"
echo "Local path: $LOCAL_PATH"
echo "Folders: $FOLDERS"
echo "Branch: $BRANCH"

# Check dependencies
command -v git >/dev/null 2>&1 || { echo "git not found; install git." >&2; exit 1; }
command -v rsync >/dev/null 2>&1 || { echo "rsync not found; install rsync." >&2; exit 1; }
if ! command -v git-lfs >/dev/null 2>&1; then
  echo "git-lfs not found; installing is recommended. Please install git-lfs and run 'git lfs install'." >&2
  echo "On macOS: brew install git-lfs && git lfs install" >&2
  read -p "Continue without git-lfs? [y/N]: " c
  if [[ "$c" != "y" && "$c" != "Y" ]]; then
    exit 1
  fi
fi

# Prepare clone URL (do NOT embed token in the URL)
CLONE_URL="https://huggingface.co/datasets/${REPO_ID}.git"

# If HF_TOKEN is provided, use a temporary GIT_ASKPASS helper so the token
# is not exposed on the command line or process list. The helper prints the
# token when git prompts for a password. We keep the helper for the duration
# of the script (so pushes work) and remove it on exit.
if [[ -n "$HF_TOKEN" ]]; then
  ASKPASS_SCRIPT=$(mktemp -t hf_askpass.XXXXXX)
  # Write an askpass helper that prints the token from the environment.
  # Use a quoted heredoc so $HF_TOKEN is not expanded into the file.
  cat > "$ASKPASS_SCRIPT" <<'ASKPASS_EOF'
#!/usr/bin/env sh
# GIT_ASKPASS helper: print HF_TOKEN from the environment (do not echo a newline)
printf "%s" "$HF_TOKEN"
ASKPASS_EOF
  chmod 700 "$ASKPASS_SCRIPT"
  export GIT_ASKPASS="$ASKPASS_SCRIPT"
  # Prevent git from falling back to terminal prompting
  export GIT_TERMINAL_PROMPT=0

  cleanup_askpass() {
    unset GIT_ASKPASS
    unset GIT_TERMINAL_PROMPT
    rm -f "$ASKPASS_SCRIPT" || true
  }
  trap cleanup_askpass EXIT
fi

# Clone the repo
if [[ -d "$CLONE_DIR" ]]; then
  echo "Removing existing clone dir $CLONE_DIR"
  rm -rf "$CLONE_DIR"
fi

echo "Cloning ${CLONE_URL} -> ${CLONE_DIR}"
if ! git clone --depth 1 --branch "$BRANCH" "$CLONE_URL" "$CLONE_DIR"; then
  echo "Initial clone failed; trying full clone (no depth)"
  git clone --branch "$BRANCH" "$CLONE_URL" "$CLONE_DIR"
fi

pushd "$CLONE_DIR" >/dev/null

# Configure git user if not set
if ! git config user.email >/dev/null; then
  git config user.email "uploader@example.com"
fi
if ! git config user.name >/dev/null; then
  git config user.name "LDData uploader"
fi

# Ensure branch exists locally
git checkout -B "$BRANCH"

# Set up git-lfs patterns (only add if git-lfs available)
if command -v git-lfs >/dev/null 2>&1; then
  echo "Configuring git-lfs patterns: ${LFS_PATTERNS[*]}"
  for pat in "${LFS_PATTERNS[@]}"; do
    git lfs track --no-update "$pat" || true
  done
  # Ensure .gitattributes is added
  git add .gitattributes || true
  git commit -m "Add git-lfs tracking patterns" --allow-empty || true
fi

# Helper to build rsync exclude args
RSYNC_EXCLUDE_ARGS=()
for ex in "${EXCLUDES[@]}"; do
  RSYNC_EXCLUDE_ARGS+=(--exclude "$ex")
done

# Copy function: copy a single folder or file into the clone preserving path
copy_item() {
  local item="$1"
  echo "Processing: $item"
  if [[ -d "$LOCAL_PATH/$item" ]]; then
    mkdir -p "$(dirname "$item")"
    rsync -av --delete "${RSYNC_EXCLUDE_ARGS[@]}" "$LOCAL_PATH/$item" ./
  elif [[ -f "$LOCAL_PATH/$item" ]]; then
    mkdir -p "$(dirname "$item")"
    rsync -av "${RSYNC_EXCLUDE_ARGS[@]}" "$LOCAL_PATH/$item" ./
  else
    echo "Warning: $item not found in $LOCAL_PATH; skipping"
  fi
}

# Commit & push a path (folder or file)
commit_and_push() {
  local path="$1"
  git add --all "$path" || true
  if git diff --staged --quiet; then
    echo "No changes staged for $path"
    return
  fi
  git commit -m "Upload $path" || true
  echo "Pushing $path to origin/$BRANCH"
  git push origin "$BRANCH"
}

# If folders list is empty, upload whole workspace excluding excludes
if [[ -z "$FOLDERS" ]]; then
  echo "No --folders provided; copying whole local tree (respecting excludes)."
  rsync -av --delete "${RSYNC_EXCLUDE_ARGS[@]}" "$LOCAL_PATH/" ./
  commit_and_push "."
else
  # iterate comma-separated list
  IFS=',' read -ra ITEMS <<< "$FOLDERS"
  for it in "${ITEMS[@]}"; do
    it_trimmed=$(echo "$it" | sed 's/^\s*//;s/\s*$//')
    if [[ -z "$it_trimmed" ]]; then
      continue
    fi
    copy_item "$it_trimmed"
    commit_and_push "$it_trimmed"
    # pause between folder pushes to avoid network bursts
    sleep 3
  done
fi

# Final push of any remaining changes
git add --all || true
if ! git diff --staged --quiet; then
  git commit -m "Upload remaining files" || true
  git push origin "$BRANCH"
fi

popd >/dev/null

echo "Upload complete. Repository at: https://huggingface.co/datasets/${REPO_ID}"

# End of script
