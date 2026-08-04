import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.infra.database import AsyncSessionLocal
from app.infra.redis import close_redis
from app.models.project import Task
from app.routers import assets, auth, chapters, chat, drama, generate, health, projects, tasks, user

logger = logging.getLogger(__name__)


async def recover_zombie_tasks():
    """启动时恢复僵尸任务：标记长时间 running 的任务为 failed"""
    async with AsyncSessionLocal() as db:
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
            result = await db.execute(
                select(Task).where(
                    Task.status == "running",
                    Task.updated_at < cutoff,
                )
            )
            zombie_tasks = result.scalars().all()
            for task in zombie_tasks:
                task.status = "failed"
                task.error_msg = "Worker 重启导致任务中断"
                logger.warning(f"Recovered zombie task {task.id} ({task.task_type})")
            await db.commit()
            if zombie_tasks:
                logger.info(f"Recovered {len(zombie_tasks)} zombie tasks")
        except Exception as e:
            logger.error(f"Failed to recover zombie tasks: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await recover_zombie_tasks()
    yield
    await close_redis()


app = FastAPI(
    title="AI Novel Studio",
    description="AI 小说 & 短剧创作工作台",
    version="0.1.0",
    lifespan=lifespan,
)

cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:5174").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in cors_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(chapters.router, prefix="/api", tags=["chapters"])
app.include_router(tasks.router, prefix="/api", tags=["tasks"])
app.include_router(generate.router, prefix="/api", tags=["generate"])
app.include_router(assets.router, prefix="/api", tags=["assets"])
app.include_router(drama.router, prefix="/api", tags=["drama"])
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(user.router, prefix="/api", tags=["user"])
