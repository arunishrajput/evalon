"""Stage 3: static analysis. Every analyzer is independently fault-tolerant —
a failed tool records an error string and contributes nothing to the report
rather than crashing the pipeline (spec P3)."""

import ast
import asyncio
import json
import logging
import re
from pathlib import Path

from pydantic import BaseModel
from radon.complexity import cc_visit
from radon.metrics import mi_visit

from app.core.exceptions import StaticAnalysisError
from app.utils.file_utils import FileEntry, read_text_file_safe

logger = logging.getLogger("evalon.static_analysis")

_ESLINT_CONFIG_DIR = Path(__file__).parent / "eslint_configs"
_SUBPROCESS_TIMEOUT_SECONDS = 90
_HIGH_COMPLEXITY_THRESHOLD = 10


class ComplexityFinding(BaseModel):
    file: str
    function_name: str
    complexity: int
    rank: str


class RadonReport(BaseModel):
    functions_analyzed: int = 0
    average_complexity: float = 0.0
    high_complexity_functions: list[ComplexityFinding] = []
    average_maintainability_index: float = 0.0


class LintFinding(BaseModel):
    file: str
    line: int
    rule_id: str | None
    message: str
    severity: str


class FileStructureReport(BaseModel):
    has_tests: bool = False
    has_ci_config: bool = False
    has_dockerfile: bool = False
    has_env_example: bool = False
    has_gitignore: bool = False
    has_license: bool = False


class DocumentationCoverage(BaseModel):
    documented: int = 0
    total: int = 0

    @property
    def ratio(self) -> float:
        return self.documented / self.total if self.total else 0.0


class StaticAnalysisReport(BaseModel):
    radon: RadonReport = RadonReport()
    semgrep_findings: list[LintFinding] = []
    eslint_findings: list[LintFinding] = []
    file_structure: FileStructureReport = FileStructureReport()
    documentation_coverage: DocumentationCoverage = DocumentationCoverage()
    errors: list[str] = []


# --- radon (in-process, per spec's stack it's a Python library dependency) ---


def _run_radon(python_files: list[FileEntry]) -> RadonReport:
    findings: list[ComplexityFinding] = []
    complexities: list[int] = []
    mi_scores: list[float] = []

    for entry in python_files:
        source = read_text_file_safe(entry.absolute_path)
        if not source:
            continue
        try:
            for block in cc_visit(source):
                complexities.append(block.complexity)
                if block.complexity > _HIGH_COMPLEXITY_THRESHOLD:
                    findings.append(
                        ComplexityFinding(
                            file=entry.relative_path,
                            function_name=block.name,
                            complexity=block.complexity,
                            rank=_complexity_rank(block.complexity),
                        )
                    )
            mi_scores.append(mi_visit(source, multi=True))
        except SyntaxError:
            continue

    return RadonReport(
        functions_analyzed=len(complexities),
        average_complexity=round(sum(complexities) / len(complexities), 2) if complexities else 0.0,
        high_complexity_functions=findings,
        average_maintainability_index=round(sum(mi_scores) / len(mi_scores), 2) if mi_scores else 0.0,
    )


def _complexity_rank(complexity: int) -> str:
    if complexity <= 5:
        return "A"
    if complexity <= 10:
        return "B"
    if complexity <= 20:
        return "C"
    if complexity <= 30:
        return "D"
    return "F"


# --- semgrep (CLI subprocess + --json; no stable embeddable Python API) ---


async def _run_semgrep(root: Path, configs: list[str]) -> list[LintFinding]:
    args = ["semgrep", "--json", "--quiet", "--timeout", "60"]
    for config in configs:
        args += ["--config", config]
    args.append(str(root))

    stdout = await _run_subprocess(args, cwd=root)
    if stdout is None:
        raise StaticAnalysisError("semgrep did not run (missing binary, timeout, or process error)")
    try:
        results = json.loads(stdout).get("results", [])
    except json.JSONDecodeError as exc:
        raise StaticAnalysisError("semgrep produced unparseable output") from exc

    return [
        LintFinding(
            file=str(Path(r["path"]).relative_to(root)) if Path(r["path"]).is_absolute() else r["path"],
            line=r.get("start", {}).get("line", 0),
            rule_id=r.get("check_id"),
            message=r.get("extra", {}).get("message", ""),
            severity=r.get("extra", {}).get("severity", "INFO"),
        )
        for r in results
    ]


# --- ESLint (CLI subprocess, global install — never a per-repo `npm install`) ---


async def _run_eslint(root: Path, extensions: list[str], config_name: str) -> list[LintFinding]:
    config_path = _ESLINT_CONFIG_DIR / config_name
    args = [
        "eslint",
        "--no-eslintrc",
        "--config",
        str(config_path),
        "--ext",
        ",".join(extensions),
        "--format",
        "json",
        "--no-error-on-unmatched-pattern",
        ".",
    ]
    stdout = await _run_subprocess(args, cwd=root)
    if stdout is None:
        raise StaticAnalysisError("eslint did not run (missing binary, timeout, or process error)")
    try:
        file_results = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise StaticAnalysisError("eslint produced unparseable output") from exc

    findings = []
    for file_result in file_results:
        rel_path = str(Path(file_result["filePath"]).relative_to(root))
        for message in file_result.get("messages", []):
            findings.append(
                LintFinding(
                    file=rel_path,
                    line=message.get("line", 0),
                    rule_id=message.get("ruleId"),
                    message=message.get("message", ""),
                    severity="error" if message.get("severity") == 2 else "warning",
                )
            )
    return findings


async def _run_subprocess(args: list[str], cwd: Path) -> str | None:
    """ESLint exits non-zero when it finds lint errors — that's expected and
    NOT a failure signal here; only a timeout, missing binary, or unparseable
    output means the analyzer itself failed."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *args, cwd=cwd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=_SUBPROCESS_TIMEOUT_SECONDS)
    except (asyncio.TimeoutError, FileNotFoundError, OSError) as exc:
        logger.warning("Static analysis subprocess %s failed: %s", args[0], exc)
        return None
    return stdout.decode("utf-8", errors="replace")


# --- file structure ---

_TEST_DIR_PATTERN = re.compile(r"(^|/)(tests?|__tests__|spec)(/|$)", re.IGNORECASE)


def _analyze_file_structure(files: list[FileEntry]) -> FileStructureReport:
    root_names = {f.relative_path for f in files if "/" not in f.relative_path}
    return FileStructureReport(
        has_tests=any(_TEST_DIR_PATTERN.search(f.relative_path) for f in files),
        has_ci_config=any(
            f.relative_path.startswith(".github/workflows/") or f.relative_path == ".gitlab-ci.yml"
            for f in files
        ),
        has_dockerfile="Dockerfile" in root_names,
        has_env_example=bool({".env.example", ".env.sample", ".env.template"} & root_names),
        has_gitignore=".gitignore" in root_names,
        has_license=bool({"LICENSE", "LICENSE.md", "LICENSE.txt"} & root_names),
    )


# --- documentation coverage ---


def _python_doc_coverage(python_files: list[FileEntry]) -> tuple[int, int]:
    documented = total = 0
    for entry in python_files:
        source = read_text_file_safe(entry.absolute_path)
        if not source:
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                total += 1
                if ast.get_docstring(node):
                    documented += 1
    return documented, total


_JSDOC_FUNCTION_PATTERN = re.compile(
    r"(/\*\*.*?\*/\s*)?^\s*(export\s+)?(async\s+)?function\s+\w+\s*\(", re.MULTILINE | re.DOTALL
)


def _js_doc_coverage(js_files: list[FileEntry]) -> tuple[int, int]:
    documented = total = 0
    for entry in js_files:
        source = read_text_file_safe(entry.absolute_path)
        if not source:
            continue
        for match in _JSDOC_FUNCTION_PATTERN.finditer(source):
            total += 1
            if match.group(1):
                documented += 1
    return documented, total


# --- orchestration ---


async def run_static_analysis(root: Path, files: list[FileEntry]) -> StaticAnalysisReport:
    python_files = [f for f in files if f.language == "Python"]
    js_files = [f for f in files if f.language in ("JavaScript",)]
    ts_files = [f for f in files if f.language in ("TypeScript",)]

    errors: list[str] = []
    radon_report = RadonReport()
    if python_files:
        try:
            radon_report = _run_radon(python_files)
        except Exception as exc:  # noqa: BLE001 - analyzer must never crash the pipeline
            logger.error("radon analysis failed: %s", exc, exc_info=True)
            errors.append("Complexity analysis (radon) failed and was skipped.")

    semgrep_configs = ["p/default"] + (["p/python"] if python_files else [])
    try:
        semgrep_findings = await _run_semgrep(root, semgrep_configs)
    except Exception as exc:  # noqa: BLE001
        logger.error("semgrep analysis failed: %s", exc, exc_info=True)
        errors.append("Security analysis (semgrep) failed and was skipped.")
        semgrep_findings = []

    eslint_findings: list[LintFinding] = []
    try:
        if js_files:
            eslint_findings += await _run_eslint(root, ["js", "jsx", "mjs"], "js.eslintrc.json")
        if ts_files:
            eslint_findings += await _run_eslint(root, ["ts", "tsx"], "ts.eslintrc.json")
    except Exception as exc:  # noqa: BLE001
        logger.error("eslint analysis failed: %s", exc, exc_info=True)
        errors.append("Lint analysis (ESLint) failed and was skipped.")

    py_documented, py_total = _python_doc_coverage(python_files)
    js_documented, js_total = _js_doc_coverage(js_files + ts_files)

    return StaticAnalysisReport(
        radon=radon_report,
        semgrep_findings=semgrep_findings,
        eslint_findings=eslint_findings,
        file_structure=_analyze_file_structure(files),
        documentation_coverage=DocumentationCoverage(
            documented=py_documented + js_documented, total=py_total + js_total
        ),
        errors=errors,
    )
