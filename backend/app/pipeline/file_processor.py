"""Stage 2: file tree, language detection, project type, dependency manifest,
README quality scoring, and tech stack extraction."""

import json
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from app.utils.file_utils import FileEntry, build_file_tree, language_breakdown, read_text_file_safe

_PROJECT_TYPE_MARKERS: list[tuple[str, str]] = [
    ("package.json", "Node.js"),
    ("go.mod", "Go"),
    ("Cargo.toml", "Rust"),
    ("pom.xml", "Java"),
    ("build.gradle", "Java"),
    ("requirements.txt", "Python"),
    ("pyproject.toml", "Python"),
    ("setup.py", "Python"),
]

_README_NAMES = {"readme.md", "readme.rst", "readme.txt", "readme"}

_SETUP_KEYWORDS = ("install", "setup", "getting started", "quick start", "prerequisites")
_DEMO_KEYWORDS = ("demo", "live at", "try it", "deployed at")
_ARCHITECTURE_KEYWORDS = ("architecture", "```mermaid", "design overview")

_DEPENDENCY_DISPLAY_NAMES: dict[str, str] = {
    "fastapi": "FastAPI",
    "flask": "Flask",
    "django": "Django",
    "express": "Express",
    "react": "React",
    "react-dom": "React",
    "next": "Next.js",
    "vue": "Vue",
    "@angular/core": "Angular",
    "svelte": "Svelte",
    "sqlalchemy": "SQLAlchemy",
    "psycopg2": "PostgreSQL",
    "psycopg2-binary": "PostgreSQL",
    "asyncpg": "PostgreSQL",
    "pg": "PostgreSQL",
    "mongoose": "MongoDB",
    "pymongo": "MongoDB",
    "redis": "Redis",
    "tensorflow": "TensorFlow",
    "torch": "PyTorch",
    "langchain": "LangChain",
    "langgraph": "LangGraph",
    "openai": "OpenAI API",
    "tailwindcss": "Tailwind CSS",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "scikit-learn": "scikit-learn",
}


@dataclass
class ReadmeAnalysis:
    content: str | None
    has_description: bool = False
    has_setup_instructions: bool = False
    has_demo_link: bool = False
    has_architecture_diagram: bool = False
    has_badges: bool = False
    quality_score: int = 0


@dataclass
class ProjectAnalysis:
    project_type: str
    primary_language: str | None
    language_breakdown: dict[str, int]
    dependency_manifest: dict[str, list[str]]
    readme: ReadmeAnalysis
    tech_stack: list[str]
    files: list[FileEntry] = field(repr=False)


def detect_project_type(files: list[FileEntry]) -> str:
    root_level_names = {f.relative_path for f in files if "/" not in f.relative_path}
    for marker, project_type in _PROJECT_TYPE_MARKERS:
        if marker in root_level_names:
            return project_type
    return "Unknown"


def _find_root_file(files: list[FileEntry], names: set[str]) -> FileEntry | None:
    for entry in files:
        if "/" not in entry.relative_path and entry.relative_path.lower() in names:
            return entry
    return None


def analyze_readme(files: list[FileEntry]) -> ReadmeAnalysis:
    readme_entry = _find_root_file(files, _README_NAMES)
    if readme_entry is None:
        return ReadmeAnalysis(content=None)

    content = read_text_file_safe(readme_entry.absolute_path) or ""
    lower = content.lower()
    top_section = lower[:400]

    analysis = ReadmeAnalysis(
        content=content,
        has_description=len(content.strip()) > 100,
        has_setup_instructions=any(kw in lower for kw in _SETUP_KEYWORDS),
        has_demo_link=any(kw in lower for kw in _DEMO_KEYWORDS) or "http" in lower and "demo" in lower,
        has_architecture_diagram=any(kw in lower for kw in _ARCHITECTURE_KEYWORDS),
        has_badges=bool(re.search(r"!\[[^\]]*\]\(https?://", top_section)),
    )
    analysis.quality_score = sum(
        20
        for flag in (
            analysis.has_description,
            analysis.has_setup_instructions,
            analysis.has_demo_link,
            analysis.has_architecture_diagram,
            analysis.has_badges,
        )
        if flag
    )
    return analysis


def _parse_package_json(content: str) -> list[str]:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return []
    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
    return list(deps.keys())


def _parse_requirements_txt(content: str) -> list[str]:
    names = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        name = re.split(r"[<>=!~\[; ]", line, maxsplit=1)[0].strip()
        if name:
            names.append(name.lower())
    return names


def _parse_pyproject_toml(content: str) -> list[str]:
    try:
        data = tomllib.loads(content)
    except tomllib.TOMLDecodeError:
        return []
    deps = data.get("project", {}).get("dependencies", [])
    names = []
    for dep in deps:
        name = re.split(r"[<>=!~\[; ]", dep, maxsplit=1)[0].strip()
        if name:
            names.append(name.lower())
    poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
    names.extend(name.lower() for name in poetry_deps if name.lower() != "python")
    return names


def parse_dependency_manifest(files: list[FileEntry]) -> dict[str, list[str]]:
    manifest: dict[str, list[str]] = {}

    package_json = _find_root_file(files, {"package.json"})
    if package_json:
        content = read_text_file_safe(package_json.absolute_path)
        if content:
            manifest["npm"] = _parse_package_json(content)

    requirements = _find_root_file(files, {"requirements.txt"})
    if requirements:
        content = read_text_file_safe(requirements.absolute_path)
        if content:
            manifest["pip"] = _parse_requirements_txt(content)

    pyproject = _find_root_file(files, {"pyproject.toml"})
    if pyproject:
        content = read_text_file_safe(pyproject.absolute_path)
        if content:
            manifest.setdefault("pip", [])
            manifest["pip"] = list({*manifest["pip"], *_parse_pyproject_toml(content)})

    return manifest


# Documentation/config file counts (esp. Markdown in docs-heavy repos) can
# outnumber actual source files — excluded from "primary language" and tech
# stack candidacy so a Python project with lots of docs doesn't get labeled
# "Markdown".
_NON_PRIMARY_LANGUAGES = {"Markdown", "JSON", "YAML"}


def _primary_candidate_languages(lang_breakdown: dict[str, int]) -> dict[str, int]:
    filtered = {lang: count for lang, count in lang_breakdown.items() if lang not in _NON_PRIMARY_LANGUAGES}
    return filtered or lang_breakdown


def extract_tech_stack(
    files: list[FileEntry], dependency_manifest: dict[str, list[str]], lang_breakdown: dict[str, int]
) -> list[str]:
    tech_stack: list[str] = []

    for language in list(_primary_candidate_languages(lang_breakdown).keys())[:2]:
        tech_stack.append(language)

    for package_names in dependency_manifest.values():
        for package_name in package_names:
            display_name = _DEPENDENCY_DISPLAY_NAMES.get(package_name.lower())
            if display_name and display_name not in tech_stack:
                tech_stack.append(display_name)

    root_names = {f.relative_path for f in files if "/" not in f.relative_path}
    if "Dockerfile" in root_names:
        tech_stack.append("Docker")
    if "docker-compose.yml" in root_names or "docker-compose.yaml" in root_names:
        tech_stack.append("Docker Compose")
    if any(f.relative_path.startswith(".github/workflows/") for f in files):
        tech_stack.append("GitHub Actions")

    return tech_stack


def analyze_project(root: Path) -> ProjectAnalysis:
    files = build_file_tree(root)
    lang_breakdown = language_breakdown(files)
    dependency_manifest = parse_dependency_manifest(files)
    tech_stack = extract_tech_stack(files, dependency_manifest, lang_breakdown)

    return ProjectAnalysis(
        project_type=detect_project_type(files),
        primary_language=next(iter(_primary_candidate_languages(lang_breakdown)), None),
        language_breakdown=lang_breakdown,
        dependency_manifest=dependency_manifest,
        readme=analyze_readme(files),
        tech_stack=tech_stack,
        files=files,
    )
