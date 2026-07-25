"""Synthetic test repository fixture — a small, deterministic file tree so
pipeline tests don't depend on network access or a real GitHub clone."""

from pathlib import Path

import pytest

_README = """# Sample Project

This project solves the problem of demonstrating EVALON's static analysis
pipeline against a small, deterministic, hand-built repository fixture.

## Installation

Run `pip install -r requirements.txt` to get started.

## Demo

A live demo is available at https://example.com/demo.

## Architecture

See the architecture diagram below.

![build](https://img.shields.io/badge/build-passing-green)
"""

_MAIN_PY = '''
def documented_function(x: int) -> int:
    """Doubles the input."""
    return x * 2


def undocumented_function(x, y, z, w, v):
    if x > 0:
        if y > 0:
            if z > 0:
                if w > 0:
                    if v > 0:
                        return x + y + z + w + v
                    return 1
                return 2
            return 3
        return 4
    if x == 1:
        return 10
    elif x == 2:
        return 20
    elif x == 3:
        return 30
    elif x == 4:
        return 40
    elif x == 5:
        return 50
    elif x == 6:
        return 60
    elif x == 7:
        return 70
    return 5


class DocumentedClass:
    """A documented class."""

    def method(self):
        pass
'''

_CI_WORKFLOW = "name: CI\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n"


@pytest.fixture
def synthetic_repo(tmp_path: Path) -> Path:
    root = tmp_path / "synthetic_repo"
    root.mkdir()
    (root / "README.md").write_text(_README)
    (root / "requirements.txt").write_text("fastapi==0.115.0\nsqlalchemy>=2.0\n# a comment\n")
    (root / "main.py").write_text(_MAIN_PY)
    (root / "LICENSE").write_text("MIT License")
    (root / ".gitignore").write_text("__pycache__/\n*.pyc\n")
    (root / "Dockerfile").write_text("FROM python:3.11-slim\n")

    (root / "tests").mkdir()
    (root / "tests" / "test_main.py").write_text("def test_ok():\n    assert True\n")

    workflows = root / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text(_CI_WORKFLOW)

    return root
