import pytest
from app.worker import celery_app

@pytest.fixture(scope="session", autouse=True)
def configure_celery_eager():
    """
    Enables synchronous/eager execution of Celery tasks during tests.
    This guarantees that tasks triggered by endpoints (like matches or resume parsing)
    run in-process and finish execution before API responses are asserted.
    """
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    celery_app.conf.task_store_eager_result = True
