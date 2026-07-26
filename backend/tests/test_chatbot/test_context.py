"""System prompt assembly and conversation-history formatting — pure
functions, no DB or model calls."""

from app.chatbot.context import build_prompt_with_history, build_system_prompt
from app.models.chat import ChatMessage, ChatRole
from app.models.repo_embedding import RepoEmbedding


def test_build_system_prompt_includes_participant_and_fixed_context():
    prompt = build_system_prompt(
        participant_name="Ada",
        repo_summary_chunk="A FastAPI project.",
        evaluation_report_chunk="Scored 80/100.",
        retrieved_chunks=[],
    )
    assert "Ada" in prompt
    assert "A FastAPI project." in prompt
    assert "Scored 80/100." in prompt


def test_build_system_prompt_formats_retrieved_chunks_with_file_label():
    chunk = RepoEmbedding(chunk_type="code", chunk_content="def f(): pass", chunk_metadata={"file": "a.py"})
    prompt = build_system_prompt(
        participant_name="Ada", repo_summary_chunk="summary", evaluation_report_chunk="report",
        retrieved_chunks=[chunk],
    )
    assert "def f(): pass" in prompt
    assert "a.py" in prompt
    assert "[code" in prompt


def test_build_system_prompt_handles_missing_fixed_chunks_and_no_retrieval():
    prompt = build_system_prompt(
        participant_name="Ada", repo_summary_chunk=None, evaluation_report_chunk=None, retrieved_chunks=[],
    )
    assert "Not available for this submission." in prompt
    assert "No additional context was retrieved" in prompt


def test_build_prompt_with_history_formats_turns_in_order():
    history = [
        ChatMessage(role=ChatRole.USER, content="Why did I lose points?"),
        ChatMessage(role=ChatRole.ASSISTANT, content="Mostly missing tests."),
    ]

    prompt = build_prompt_with_history(history, "How do I add tests?")

    lines = prompt.splitlines()
    assert lines[0] == "Participant: Why did I lose points?"
    assert lines[1] == "Mentor: Mostly missing tests."
    assert lines[2] == "Participant: How do I add tests?"
    assert lines[3] == "Mentor:"


def test_build_prompt_with_history_handles_empty_history():
    prompt = build_prompt_with_history([], "First question")
    assert prompt == "Participant: First question\nMentor:"
