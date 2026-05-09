from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.infra.redis import close_redis
from app.routers import assets, auth, chapters, chat, drama, generate, health, projects, tasks


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_redis()


app = FastAPI(
    title="AI Novel Studio",
    description="AI 小说 & 短剧创作工作台",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
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
