from celery import Celery
from app.core.config import settings

celery_app = Celery("traffic_worker", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_routes = {"app.workers.tasks.process_job": {"queue": "video"}}
celery_app.conf.task_acks_late = True
celery_app.conf.worker_prefetch_multiplier = 1
