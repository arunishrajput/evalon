"""Shared RepoContext fixture for agent-level tests — a fully-formed context
so each agent's prompt-rendering path is exercised, not just its parsing."""

import pytest

from app.pipeline.context_builder import CodeSample, RepoContext
from app.pipeline.static_analysis import DocumentationCoverage, RadonReport, StaticAnalysisReport


@pytest.fixture
def repo_context() -> RepoContext:
    return RepoContext(
        submission_id="sub-1",
        hackathon_id="hack-1",
        repo_url="https://github.com/example/project",
        repo_name="project",
        repo_description="An example project",
        project_type="Python",
        primary_language="Python",
        language_breakdown={"Python": 10},
        tech_stack=["Python", "FastAPI"],
        dependency_manifest={"pip": ["fastapi"]},
        readme_content="# Project\n\nDoes something useful.",
        readme_quality_score=60,
        file_count=12,
        file_paths=["main.py", "README.md"],
        code_samples=[CodeSample(file="main.py", content="def f():\n    pass\n")],
        static_analysis=StaticAnalysisReport(
            radon=RadonReport(functions_analyzed=5, average_maintainability_index=70.0),
            documentation_coverage=DocumentationCoverage(documented=2, total=5),
        ),
    )


class FakeLLM:
    """Stub LLMProvider — returns a fixed response or raises a fixed exception,
    and records the last prompt/system it was called with for assertions."""

    def __init__(self, response: str | None = None, exception: Exception | None = None):
        self._response = response
        self._exception = exception
        self.last_prompt: str | None = None
        self.last_system: str | None = None
        self.call_count = 0

    async def generate(self, prompt: str, system: str, *, json_mode: bool = True, timeout: int = 90) -> str:
        self.call_count += 1
        self.last_prompt = prompt
        self.last_system = system
        if self._exception:
            raise self._exception
        return self._response
