import pytest


def test_process_job_task_is_registered():
    pytest.importorskip("celery")
    from app.workers.celery_app import celery_app

    assert "app.workers.tasks.process_job" in celery_app.tasks
