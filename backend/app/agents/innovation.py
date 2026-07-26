"""Innovation Agent (spec Section 8, Agent 3) — "the most subjective agent"
per the spec's own characterization. No deterministic tool measures
"originality," so score_raw is LLM-produced, heavily grounded via a strict
schema, an anti-hallucination instruction, a worked few-shot example, and an
explicit calibration anchor."""

from app.agents.base import AgentResult, BaseEvaluator, EvidenceItem, clamp_confidence, clamp_score, parse_llm_json
from app.agents.prompt_loader import render_prompt
from app.pipeline.context_builder import RepoContext

_SYSTEM_PROMPT = (
    "You are a senior engineer judging hackathon submissions for originality and technical "
    "sophistication. You are calibrated, skeptical of generic CRUD apps, and you only cite "
    "observations you were actually given."
)


class InnovationAgent(BaseEvaluator):
    agent_id = "innovation"
    agent_name = "Innovation Agent"

    async def evaluate(
        self, repo_context: RepoContext, understanding: AgentResult | None = None, **kwargs
    ) -> AgentResult:
        details = understanding.details if understanding and not understanding.abstained else {}
        prompt = render_prompt(
            "innovation.j2",
            project_goals=details.get("project_goals") or "Not determined from repository understanding.",
            technical_approach=details.get("technical_approach") or "Not determined.",
            architecture_pattern=details.get("architecture_pattern") or "Not determined.",
            key_technologies=details.get("key_technologies") or repo_context.tech_stack,
            demo_maturity=details.get("demo_maturity") or "unknown",
            tech_stack=repo_context.tech_stack,
            hackathon_problem_statement=None,
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
                "problem_originality_notes": data.get("problem_originality_notes", ""),
                "solution_creativity_notes": data.get("solution_creativity_notes", ""),
                "technical_sophistication_notes": data.get("technical_sophistication_notes", ""),
                "execution_quality_notes": data.get("execution_quality_notes", ""),
            },
        )
