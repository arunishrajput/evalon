"""Repository Understanding Agent (spec Section 8, Agent 1). Runs first so
its structured output (project goals, architecture, demo maturity) can
ground the Innovation Agent's input. score_raw is LLM-produced — no
deterministic tool measures "clarity of vision" — grounded via a strict JSON
schema, an anti-hallucination instruction, and a worked few-shot example."""

from app.agents.base import AgentResult, BaseEvaluator, EvidenceItem, clamp_confidence, clamp_score, parse_llm_json
from app.agents.prompt_loader import render_prompt
from app.pipeline.context_builder import RepoContext

_SYSTEM_PROMPT = (
    "You are a meticulous senior engineer performing project intake for a hackathon judging "
    "platform. You only describe what you can directly observe in the provided files."
)


class RepoUnderstandingAgent(BaseEvaluator):
    agent_id = "repo_understanding"
    agent_name = "Repository Understanding Agent"

    async def evaluate(self, repo_context: RepoContext, **kwargs) -> AgentResult:
        prompt = render_prompt(
            "repo_understanding.j2",
            readme_content=repo_context.readme_content,
            project_type=repo_context.project_type,
            primary_language=repo_context.primary_language,
            language_breakdown=repo_context.language_breakdown,
            dependency_manifest=repo_context.dependency_manifest,
            file_count=repo_context.file_count,
            file_paths=repo_context.file_paths[:40],
        )
        raw = await self.llm.generate(prompt, system=_SYSTEM_PROMPT, json_mode=True, timeout=self.TIMEOUT_SECONDS)
        data = parse_llm_json(raw)

        evidence = [EvidenceItem(**e) for e in data.get("evidence", [])[:10]]
        top_evidence = data.get("top_evidence") or [e.finding for e in evidence[:2]]

        return AgentResult(
            agent_id=self.agent_id,
            score_raw=clamp_score(data.get("score_raw", 50)),
            confidence=clamp_confidence(data.get("confidence", 0.5)),
            evidence=evidence,
            top_evidence=top_evidence[:2],
            strengths=data.get("strengths", [])[:10],
            weaknesses=data.get("weaknesses", [])[:10],
            reasoning=data.get("reasoning", ""),
            details={
                "project_goals": data.get("project_goals", ""),
                "target_audience": data.get("target_audience", ""),
                "technical_approach": data.get("technical_approach", ""),
                "architecture_pattern": data.get("architecture_pattern", ""),
                "key_technologies": data.get("key_technologies", []),
                "demo_maturity": data.get("demo_maturity", "unknown"),
            },
        )
