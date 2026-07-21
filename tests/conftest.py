import os
import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://resumeranker:devpassword123@127.0.0.1:5432/resumeranker")

from app.config import get_settings
get_settings.cache_clear()

from app.worker import celery_app

@pytest.fixture(scope="session", autouse=True)
def configure_celery_eager():
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    celery_app.conf.task_store_eager_result = True
    celery_app.conf.result_backend = "cache+memory://"

@pytest.fixture(scope="session", autouse=True)
def preload_embedding_model():
    try:
        from app.services.embedding import get_embedding_service
        get_embedding_service()
    except Exception as exc:
        pytest.fail(f"Failed to preload embedding model: {exc}")
