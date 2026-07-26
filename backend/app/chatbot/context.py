"""Chat context assembly (RAG) for the mentor chatbot — spec Section 9's
system prompt template and conversation-history formatting. Ollama's
/api/generate is completion-style (a single prompt string), not a chat
message array, so prior turns are folded into the prompt text rather than
passed as a separate messages list."""

from app.models.chat import ChatMessage, ChatRole
from app.models.repo_embedding import RepoEmbedding

SYSTEM_PROMPT_TEMPLATE = """You are an expert software engineering mentor. You are reviewing the \
hackathon submission of {participant_name}.

THEIR PROJECT:
{repo_summary_chunk}

THEIR EVALUATION REPORT:
{evaluation_report_chunk}

RELEVANT CONTEXT:
{retrieved_chunks}

Your role is to:
- Help them understand why they received specific scores
- Teach them engineering best practices relevant to their code
- Suggest concrete improvements with examples
- Be encouraging and educational, not discouraging
- Only reference what you can see in the provided context

Do NOT make up information about their code that isn't in the context."""

MAX_HISTORY_MESSAGES = 10


def build_system_prompt(
    *,
    participant_name: str,
    repo_summary_chunk: str | None,
    evaluation_report_chunk: str | None,
    retrieved_chunks: list[RepoEmbedding],
) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(
        participant_name=participant_name,
        repo_summary_chunk=repo_summary_chunk or "Not available for this submission.",
        evaluation_report_chunk=evaluation_report_chunk or "Not available for this submission.",
        retrieved_chunks=_format_retrieved(retrieved_chunks),
    )


def _format_retrieved(chunks: list[RepoEmbedding]) -> str:
    if not chunks:
        return "No additional context was retrieved for this question."
    parts = []
    for chunk in chunks:
        label = chunk.chunk_metadata.get("file") if chunk.chunk_metadata else None
        header = f"[{chunk.chunk_type}{f' — {label}' if label else ''}]"
        parts.append(f"{header}\n{chunk.chunk_content}")
    return "\n\n".join(parts)


def build_prompt_with_history(history: list[ChatMessage], new_message: str) -> str:
    """`history` should already be capped to the most recent MAX_HISTORY_MESSAGES,
    oldest first, and must NOT include `new_message` itself."""
    lines = []
    for message in history:
        speaker = "Participant" if message.role == ChatRole.USER else "Mentor"
        lines.append(f"{speaker}: {message.content}")
    lines.append(f"Participant: {new_message}")
    lines.append("Mentor:")
    return "\n".join(lines)
