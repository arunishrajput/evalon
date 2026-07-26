"""ARQ worker definition. `functions` is populated incrementally as each job is
implemented: ingest_repository (Phase 3), run_evaluation_pipeline,
recompute_rankings, update_hackathon_stats (Phase 4/5), generate_embeddings
(Phase 6)."""

from arq.connections import RedisSettings

from app.config import get_settings
from app.jobs.tasks import (
    generate_embeddings,
    ingest_repository,
    ping,
    recompute_rankings,
    run_evaluation_pipeline,
    update_hackathon_stats,
)

settings = get_settings()


class WorkerSettings:
    functions: list = [
        ping,
        ingest_repository,
        run_evaluation_pipeline,
        recompute_rankings,
        update_hackathon_stats,
        generate_embeddings,
    ]
    redis_settings = RedisSettings(host=settings.redis_host, port=settings.redis_port)
    max_jobs = 3  # prevents simultaneous model loads (see ModelQueueManager)
    job_timeout = 900
    keep_result = 3600
    health_check_interval = 30
    retry_jobs = True
    max_tries = 3
