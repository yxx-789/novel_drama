"""Resolve per-user LLM configuration with fallback to platform defaults."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.crypto import decrypt_api_key
from app.models.user import User


async def resolve_llm_config(user_id: str, db: AsyncSession) -> dict:
    """
    Resolve the effective LLM configuration for a given user.

    Priority:
        1. User custom config (llm_api_key_encrypted present)
           - base_url / model fall back to platform defaults if empty
        2. Platform default config (settings.LLM_*)

    Returns a dict with keys:
        api_key, base_url, model, interface_format, temperature, max_tokens, timeout
    """
    user = await db.get(User, user_id)

    if user and user.llm_api_key_encrypted:
        # User has a custom API key
        api_key = decrypt_api_key(user.llm_api_key_encrypted)
        base_url = user.llm_base_url or settings.LLM_BASE_URL
        model = user.llm_model or settings.LLM_MODEL
    else:
        # Fallback to platform default
        api_key = settings.LLM_API_KEY
        base_url = settings.LLM_BASE_URL
        model = settings.LLM_MODEL

    return {
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "interface_format": settings.LLM_INTERFACE_FORMAT,
        "temperature": settings.LLM_TEMPERATURE,
        "max_tokens": settings.LLM_MAX_TOKENS,
        "timeout": settings.LLM_TIMEOUT,
    }


async def _get_llm_config_for_task(task_id: str, db: AsyncSession) -> dict:
    """
    Helper for Celery workers: given a task_id, look up the task's project owner
    and resolve their LLM config.
    """
    from uuid import UUID

    from app.models.project import Project, Task

    task = await db.get(Task, UUID(task_id))
    if not task:
        raise RuntimeError(f"Task {task_id} not found")

    project = await db.get(Project, task.project_id)
    if not project:
        raise RuntimeError(f"Project {task.project_id} not found")

    return await resolve_llm_config(project.owner_id, db)
