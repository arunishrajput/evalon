"""Generic file-tree and text-file helpers shared by the pipeline stages.
Never loads more than MAX_READ_BYTES of any single file into memory."""

from dataclasses import dataclass
from pathlib import Path

MAX_READ_BYTES = 200_000  # ~200KB — plenty for README/source-sample purposes
BINARY_SNIFF_BYTES = 8_000

LANGUAGE_EXTENSIONS: dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".hpp": "C++",
    ".cs": "C#",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".scala": "Scala",
    ".sh": "Shell",
    ".sql": "SQL",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".vue": "Vue",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".json": "JSON",
    ".md": "Markdown",
}


@dataclass
class FileEntry:
    relative_path: str
    absolute_path: Path
    size_bytes: int
    language: str | None


def is_binary_file(path: Path) -> bool:
    """Standard heuristic: a NUL byte in the first chunk means binary."""
    try:
        with path.open("rb") as handle:
            chunk = handle.read(BINARY_SNIFF_BYTES)
    except OSError:
        return True
    return b"\x00" in chunk


def build_file_tree(root: Path) -> list[FileEntry]:
    entries: list[FileEntry] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        entries.append(
            FileEntry(
                relative_path=str(path.relative_to(root)),
                absolute_path=path,
                size_bytes=size,
                language=LANGUAGE_EXTENSIONS.get(path.suffix.lower()),
            )
        )
    return entries


def language_breakdown(files: list[FileEntry]) -> dict[str, int]:
    """File count per detected language, most common first."""
    counts: dict[str, int] = {}
    for entry in files:
        if entry.language:
            counts[entry.language] = counts.get(entry.language, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: item[1], reverse=True))


def read_text_file_safe(path: Path, max_bytes: int = MAX_READ_BYTES) -> str | None:
    """Returns the file's text content (truncated to max_bytes) or None if
    the file is binary, unreadable, or larger than 1MB (per the spec's
    binary-file-over-1MB exclusion, applied uniformly to text reads too)."""
    try:
        if path.stat().st_size > 1_000_000:
            return None
        if is_binary_file(path):
            return None
        return path.read_text(encoding="utf-8", errors="replace")[:max_bytes]
    except OSError:
        return None
