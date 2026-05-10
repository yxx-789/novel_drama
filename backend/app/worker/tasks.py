import asyncio
import logging
import uuid

from app.core.celery_app import celery_app
from app.infra.database import engine
from app.services.task_service import (
    run_architecture_task,
    run_batch_chapters_task,
    run_chapter_task,
    run_directory_task,
    run_drama_batch_task,
    run_drama_episode_task,
    run_drama_plan_task,
)

logger = logging.getLogger(__name__)


async def _run_with_cleanup(coro):
    """在独立事件循环中运行协程，结束后清理连接池。"""
    try:
        await coro
    finally:
        try:
            await engine.dispose()
        except Exception as e:
            logger.warning(f"Engine dispose warning: {e}")


@celery_app.task(bind=True)
def run_architecture(self, task_id: str):
    logger.info(f"Celery task [architecture] started for task_id={task_id}")
    asyncio.run(_run_with_cleanup(run_architecture_task(uuid.UUID(task_id))))
    return {"status": "success"}


@celery_app.task(bind=True)
def run_directory(self, task_id: str):
    logger.info(f"Celery task [directory] started for task_id={task_id}")
    asyncio.run(_run_with_cleanup(run_directory_task(uuid.UUID(task_id))))
    return {"status": "success"}


@celery_app.task(bind=True)
def run_chapter(self, task_id: str):
    logger.info(f"Celery task [chapter] started for task_id={task_id}")
    asyncio.run(_run_with_cleanup(run_chapter_task(uuid.UUID(task_id))))
    return {"status": "success"}


@celery_app.task(bind=True)
def run_batch_chapters(self, task_id: str):
    logger.info(f"Celery task [batch_chapters] started for task_id={task_id}")
    asyncio.run(_run_with_cleanup(run_batch_chapters_task(uuid.UUID(task_id))))
    return {"status": "success"}


@celery_app.task(bind=True)
def run_drama_plan(self, task_id: str):
    logger.info(f"Celery task [drama_plan] started for task_id={task_id}")
    asyncio.run(_run_with_cleanup(run_drama_plan_task(uuid.UUID(task_id))))
    return {"status": "success"}


@celery_app.task(bind=True)
def run_drama_episode(self, task_id: str):
    logger.info(f"Celery task [drama_episode] started for task_id={task_id}")
    asyncio.run(_run_with_cleanup(run_drama_episode_task(uuid.UUID(task_id))))
    return {"status": "success"}


@celery_app.task(bind=True)
def run_drama_batch(self, task_id: str):
    logger.info(f"Celery task [drama_batch] started for task_id={task_id}")
    asyncio.run(_run_with_cleanup(run_drama_batch_task(uuid.UUID(task_id))))
    return {"status": "success"}
