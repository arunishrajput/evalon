"""GitHub URL validation and repository cloning. Cloning is blocking I/O
(gitpython shells out to git) so it always runs in a thread executor from
async callers — never directly in an event loop."""

import asyncio
import re
import shutil
from pathlib import Path

import httpx
from git import Repo
from git.exc import GitCommandError

from app.core.exceptions import RepositoryIngestionError

GITHUB_URL_PATTERN = re.compile(
    r"^https://github\.com/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+?)(\.git)?/?$"
)

# Directories that are never useful for static analysis and are stripped
# immediately after clone — never analyzed, never sent to an LLM.
EXCLUDED_DIRS = {"node_modules", ".git", "venv", ".venv", "__pycache__"}

# git's partial-clone blob-size filter matches the spec's "exclude binary
# files over 1MB" rule at the network level — large blobs are never fetched.
BLOB_SIZE_LIMIT = "blob:limit=1m"


def parse_github_url(url: str) -> tuple[str, str]:
    """Returns (owner, repo). Raises RepositoryIngestionError if the URL
    isn't a well-formed github.com repository URL."""
    match = GITHUB_URL_PATTERN.match(url.strip())
    if not match:
        raise RepositoryIngestionError(
            "That doesn't look like a valid GitHub repository URL "
            "(expected https://github.com/owner/repo).",
            "invalid_repo_url",
        )
    return match.group("owner"), match.group("repo")


async def validate_repo_exists_and_public(url: str, github_token: str = "") -> dict:
    """HTTP HEAD existence check + unauthenticated GitHub API call to confirm
    the repo is public. Returns the GitHub API repo metadata dict on success."""
    owner, repo = parse_github_url(url)
    headers = {"Authorization": f"token {github_token}"} if github_token else {}

    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        try:
            head_resp = await client.head(url)
        except httpx.HTTPError as exc:
            raise RepositoryIngestionError(
                f"Could not reach {url}. Please check the URL and try again.", "repo_unreachable"
            ) from exc
        if head_resp.status_code >= 400:
            raise RepositoryIngestionError(
                "That repository could not be found. Please check the URL is correct "
                "and the repository is public.",
                "repo_not_found",
            )

        try:
            api_resp = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}", headers=headers
            )
        except httpx.HTTPError as exc:
            raise RepositoryIngestionError(
                "Could not verify the repository via the GitHub API. Please try again shortly.",
                "github_api_unreachable",
            ) from exc

    if api_resp.status_code == 404:
        raise RepositoryIngestionError(
            "That repository could not be found. Please check the URL is correct "
            "and the repository is public.",
            "repo_not_found",
        )
    if api_resp.status_code != 200:
        raise RepositoryIngestionError(
            "Could not verify the repository via the GitHub API. Please try again shortly.",
            "github_api_error",
        )

    metadata = api_resp.json()
    if metadata.get("private"):
        raise RepositoryIngestionError(
            "This repository is private. EVALON only evaluates public repositories.",
            "repo_is_private",
        )
    return metadata


def _blocking_clone(repo_url: str, dest_path: Path) -> None:
    Repo.clone_from(
        repo_url,
        dest_path,
        depth=1,
        single_branch=True,
        multi_options=[f"--filter={BLOB_SIZE_LIMIT}"],
    )


async def clone_repository(
    repo_url: str, dest_path: Path, *, timeout_seconds: int, max_size_mb: int, max_file_count: int
) -> None:
    """Shallow-clones with a blob-size filter, strips excluded directories,
    then enforces the total-size and file-count limits — cleaning up and
    raising a human-readable RepositoryIngestionError if either is exceeded."""
    dest_path.mkdir(parents=True, exist_ok=True)
    loop = asyncio.get_running_loop()
    try:
        await asyncio.wait_for(
            loop.run_in_executor(None, _blocking_clone, repo_url, dest_path),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError as exc:
        shutil.rmtree(dest_path, ignore_errors=True)
        raise RepositoryIngestionError(
            f"Cloning took longer than {timeout_seconds} seconds and was cancelled. "
            "This usually means the repository is too large.",
            "clone_timeout",
        ) from exc
    except GitCommandError as exc:
        shutil.rmtree(dest_path, ignore_errors=True)
        raise RepositoryIngestionError(
            "Git was unable to clone this repository. Please verify the URL is correct.",
            "clone_failed",
        ) from exc

    _strip_excluded_dirs(dest_path)
    _enforce_size_and_count_limits(dest_path, max_size_mb=max_size_mb, max_file_count=max_file_count)


def _strip_excluded_dirs(root: Path) -> None:
    for excluded_name in EXCLUDED_DIRS:
        for path in root.rglob(excluded_name):
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)


def _enforce_size_and_count_limits(root: Path, *, max_size_mb: int, max_file_count: int) -> None:
    total_bytes = 0
    file_count = 0
    for path in root.rglob("*"):
        if path.is_file():
            file_count += 1
            total_bytes += path.stat().st_size

    total_mb = total_bytes / (1024 * 1024)
    if file_count > max_file_count:
        shutil.rmtree(root, ignore_errors=True)
        raise RepositoryIngestionError(
            f"This repository has {file_count} files, exceeding the {max_file_count} file limit.",
            "repo_too_many_files",
        )
    if total_mb > max_size_mb:
        shutil.rmtree(root, ignore_errors=True)
        raise RepositoryIngestionError(
            f"This repository is {total_mb:.1f}MB, exceeding the {max_size_mb}MB limit.",
            "repo_too_large",
        )
