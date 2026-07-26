"""Code Quality Agent (spec Section 8, Agent 2). score_raw is ALWAYS computed
deterministically from static analysis (app.scoring.aggregator) — never a
raw LLM number, per P1 and Section 8's explicit weighted formula. The LLM's
only job is narrative interpretation: explaining WHY the metrics produced
this score, with specific file-referenced evidence. If the LLM call fails,
the agent still returns a valid (non-abstained) result with
fallback_used=True, since the score never depended on the LLM in the first
place — this agent effectively only abstains on a genuine crash or the
outer 90s timeout."""

import asyncio
import logging

from app.agents.base import AgentResult, BaseEvaluator, EvidenceItem, clamp_confidence, parse_llm_json
from app.agents.prompt_loader import render_prompt
from app.core.exceptions import ModelUnavailableError
from app.pipeline.context_builder import RepoContext
from app.pipeline.static_analysis import StaticAnalysisReport
from app.scoring.aggregator import compute_code_quality_score

logger = logging.getLogger("evalon.agents.code_quality")

_SYSTEM_PROMPT = (
    "You are a senior software engineer performing a code review grounded strictly "
    "in the deterministic metrics you are given. You never invent findings."
)


class CodeQualityAgent(BaseEvaluator):
    agent_id = "code_quality"
    agent_name = "Code Quality Agent"

    async def evaluate(self, repo_context: RepoContext, **kwargs) -> AgentResult:
        static_analysis = repo_context.static_analysis
        score_raw = compute_code_quality_score(static_analysis)

        try:
            narrative = await self._get_narrative(repo_context, score_raw)
        except (ModelUnavailableError, asyncio.TimeoutError, ValueError) as exc:
            logger.warning("Code quality narrative unavailable, using static-only fallback: %s", exc)
            return self._static_only_result(score_raw, static_analysis)

        evidence = [EvidenceItem(**e) for e in narrative.get("evidence", [])[:10]]
        top_evidence = narrative.get("top_evidence") or self._fallback_top_evidence(static_analysis)

        return AgentResult(
            agent_id=self.agent_id,
            score_raw=score_raw,
            confidence=clamp_confidence(narrative.get("confidence", 0.8)),
            evidence=evidence,
            top_evidence=top_evidence[:2],
            strengths=narrative.get("strengths", [])[:10],
            weaknesses=narrative.get("weaknesses", [])[:10],
            reasoning=narrative.get("reasoning", ""),
        )

    async def _get_narrative(self, repo_context: RepoContext, score_raw: float) -> dict:
        sa = repo_context.static_analysis
        prompt = render_prompt(
            "code_quality.j2",
            score_raw=round(score_raw, 1),
            complexity_summary=self._complexity_summary(sa),
            modularity_summary=f"maintainability index {sa.radon.average_maintainability_index:.1f}/100",
            docs_summary=f"{sa.documentation_coverage.documented}/{sa.documentation_coverage.total} documented",
            error_handling_summary=(
                f"{sa.error_handling.functions_with_handling}/{sa.error_handling.total_functions} "
                "functions with error handling"
            ),
            semgrep_summary=f"{len(sa.semgrep_findings)} findings",
            high_complexity_functions=[f.model_dump() for f in sa.radon.high_complexity_functions[:15]],
            maintainability_index=sa.radon.average_maintainability_index,
            documented=sa.documentation_coverage.documented,
            total_documentable=sa.documentation_coverage.total,
            doc_ratio_pct=round(sa.documentation_coverage.ratio * 100, 1),
            has_tests=sa.file_structure.has_tests,
            has_ci_config=sa.file_structure.has_ci_config,
            has_dockerfile=sa.file_structure.has_dockerfile,
            has_gitignore=sa.file_structure.has_gitignore,
            has_license=sa.file_structure.has_license,
            semgrep_count=len(sa.semgrep_findings),
            semgrep_findings_sample=[f.model_dump() for f in sa.semgrep_findings[:10]],
            code_samples=[s.model_dump() for s in repo_context.code_samples],
        )
        raw = await self.llm.generate(prompt, system=_SYSTEM_PROMPT, json_mode=True, timeout=self.TIMEOUT_SECONDS)
        return parse_llm_json(raw)

    @staticmethod
    def _complexity_summary(sa: StaticAnalysisReport) -> str:
        radon = sa.radon
        return (
            f"{len(radon.high_complexity_functions)}/{radon.functions_analyzed} functions exceed "
            f"complexity 10 (avg {radon.average_complexity})"
        )

    @staticmethod
    def _fallback_top_evidence(sa: StaticAnalysisReport) -> list[str]:
        items = []
        if sa.radon.high_complexity_functions:
            items.append(f"{len(sa.radon.high_complexity_functions)} functions exceed complexity threshold of 10")
        doc = sa.documentation_coverage
        if doc.total:
            items.append(f"{doc.ratio * 100:.0f}% docstring coverage across analyzed modules")
        return items or ["Static analysis completed with no major findings."]

    def _static_only_result(self, score_raw: float, sa: StaticAnalysisReport) -> AgentResult:
        top_evidence = self._fallback_top_evidence(sa)
        return AgentResult(
            agent_id=self.agent_id,
            score_raw=score_raw,
            confidence=0.5,
            evidence=[
                EvidenceItem(finding=item, impact="Contributes to the static-analysis-only score.", file_ref="")
                for item in top_evidence
            ],
            top_evidence=top_evidence[:2],
            strengths=[],
            weaknesses=[],
            reasoning=(
                "AI narrative interpretation was unavailable for this evaluation; the score above "
                "was computed entirely from deterministic static analysis (complexity, maintainability, "
                "documentation coverage, error handling, and security findings)."
            ),
            fallback_used=True,
        )
