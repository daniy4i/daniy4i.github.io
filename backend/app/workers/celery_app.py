from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "traffic_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)

# Route jobs to the "video" queue
celery_app.conf.task_routes = {
    "app.workers.tasks.process_job": {"queue": "video"},
}

# Prefer consuming from video queue by default
celery_app.conf.task_default_queue = "video"

# Safer defaults for long-running jobs
celery_app.conf.task_acks_late = True
celery_app.conf.worker_prefetch_multiplier = 1

# Silence Celery startup warning (recommended for Redis)
celery_app.conf.broker_connection_retry_on_startup = True

# Ensure tasks are registered
from app.workers import tasks as _tasks  # noqa: F401