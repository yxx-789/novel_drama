"""User-level settings: LLM configuration, profile, etc."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.crypto import decrypt_api_key, encrypt_api_key
from app.generator.llm_adapter import create_llm_adapter
from app.infra.database import get_db
from app.models.user import User
from app.routers.dependency import get_current_user
from app.services.llm_config_service import resolve_llm_config

router = APIRouter()


class LLMConfigOut(BaseModel):
    api_key: str | None
    base_url: str
    model: str
    source: str  # "user_custom" or "platform_default"


class LLMConfigUpdate(BaseModel):
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None


class LLMConfigTestPayload(BaseModel):
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None


class LLMConfigTestResult(BaseModel):
    success: bool
    message: str


@router.get("/user/llm-config", response_model=LLMConfigOut)
async def get_user_llm_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the current user's LLM configuration (decrypted)."""
    cfg = await resolve_llm_config(str(current_user.id), db)

    source = "platform_default"
    if current_user.llm_api_key_encrypted:
        source = "user_custom"

    return LLMConfigOut(
        api_key=cfg["api_key"] or None,
        base_url=cfg["base_url"],
        model=cfg["model"],
        source=source,
    )


@router.put("/user/llm-config", response_model=LLMConfigOut)
async def update_user_llm_config(
    payload: LLMConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the user's LLM configuration. api_key=null clears the custom key."""
    if "api_key" in payload.model_fields_set:
        if payload.api_key is None or payload.api_key == "":
            current_user.llm_api_key_encrypted = None
        else:
            current_user.llm_api_key_encrypted = encrypt_api_key(payload.api_key)

    if "base_url" in payload.model_fields_set:
        current_user.llm_base_url = payload.base_url or None

    if "model" in payload.model_fields_set:
        current_user.llm_model = payload.model or None

    current_user.llm_config_updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(current_user)

    cfg = await resolve_llm_config(str(current_user.id), db)
    return LLMConfigOut(
        api_key=cfg["api_key"] or None,
        base_url=cfg["base_url"],
        model=cfg["model"],
        source="user_custom" if current_user.llm_api_key_encrypted else "platform_default",
    )


@router.post("/user/llm-config/test", response_model=LLMConfigTestResult)
async def test_user_llm_config(
    payload: LLMConfigTestPayload | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Test an LLM configuration by sending a lightweight request."""
    # Determine which config to test
    # 1. 先读取已保存的配置作为基准
    cfg = await resolve_llm_config(str(current_user.id), db)
    api_key = cfg["api_key"]
    base_url = cfg["base_url"]
    model = cfg["model"]

    # 2. 如果前端传了 preview 值，覆盖对应字段
    if payload:
        if payload.api_key is not None:
            api_key = payload.api_key or ""
        if payload.base_url is not None:
            base_url = payload.base_url or settings.LLM_BASE_URL
        if payload.model is not None:
            model = payload.model or settings.LLM_MODEL

    if not api_key:
        return LLMConfigTestResult(
            success=False,
            message="未配置 API Key，请在设置中添加",
        )

    try:
        adapter = create_llm_adapter(
            interface_format=settings.LLM_INTERFACE_FORMAT,
            base_url=base_url,
            model_name=model,
            api_key=api_key,
            temperature=0.7,
            max_tokens=10,
            timeout=10,
        )
        result = await adapter.invoke("Hi")
        if result:
            return LLMConfigTestResult(
                success=True,
                message=f"连接成功，模型响应: {result[:50]}",
            )
        return LLMConfigTestResult(
            success=False,
            message="模型返回空响应",
        )
    except Exception as e:
        err_msg = str(e) or "未知错误，请检查网络或 API 配置"
        return LLMConfigTestResult(
            success=False,
            message=f"连接失败: {err_msg}",
        )
