"""ARQ job task definitions. Domain jobs (ingest_repository, run_evaluation_pipeline,
generate_embeddings, recompute_rankings, update_hackathon_stats) are added in
Phases 3, 4, 5, and 6 as their dependencies come online."""

import logging

logger = logging.getLogger("evalon.jobs")


async def ping(ctx: dict) -> str:
    """Trivial job used to verify the ARQ worker is actually picking up and
    executing jobs from the queue (used by Phase 1 infra verification and,
    later, by `make model-status`-style operational checks)."""
    logger.info("ping job executed")
    return "pong"
