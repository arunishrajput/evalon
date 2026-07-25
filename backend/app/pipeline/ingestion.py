"""Stage 1: repository ingestion. Clones to /workspace/repos/{submission_id}/
— submission_id as the subfolder name prevents path traversal from a
malicious repo_url (the clone target is never derived from user input)."""

import shutil
from pathlib import Path

from app.utils.git_utils import clone_repository


def workspace_path(workspace_dir: str, submission_id: str) -> Path:
    return Path(workspace_dir) / submission_id


async def ingest_repository(
    repo_url: str,
    submission_id: str,
    *,
    workspace_dir: str,
    timeout_seconds: int,
    max_size_mb: int,
    max_file_count: int,
) -> Path:
    dest = workspace_path(workspace_dir, submission_id)
    await clone_repository(
        repo_url,
        dest,
        timeout_seconds=timeout_seconds,
        max_size_mb=max_size_mb,
        max_file_count=max_file_count,
    )
    return dest


def cleanup_workspace(workspace_dir: str, submission_id: str) -> None:
    shutil.rmtree(workspace_path(workspace_dir, submission_id), ignore_errors=True)
