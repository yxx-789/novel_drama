import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.database import get_db
from app.models.user import User
from app.routers.dependency import get_current_user
from app.schemas.chat import (
    ChatMessageCreate,
    ChatMessageOut,
    ChatSessionCreate,
    ChatSessionDetailOut,
    ChatSessionOut,
)
from app.models.chat import ChatMessage
from app.models.chat import ChatSession
from app.services.chat_service import (
    create_session,
    get_session_with_messages,
    list_sessions,
    send_message,
)

router = APIRouter()


@router.get("/projects/{project_id}/chat-sessions", response_model=list[ChatSessionOut])
async def get_project_chat_sessions(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sessions = await list_sessions(
        db, user_id=str(current_user.id), project_id=str(project_id)
    )
    return sessions


@router.get("/chat-sessions", response_model=list[ChatSessionOut])
async def get_user_chat_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sessions = await list_sessions(db, user_id=str(current_user.id))
    return sessions


@router.post("/chat-sessions", response_model=ChatSessionOut)
async def create_chat_session(
    req: ChatSessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = await create_session(
        db,
        user_id=str(current_user.id),
        project_id=str(req.project_id) if req.project_id else None,
        title=req.title,
    )
    return session


@router.get("/chat-sessions/{session_id}", response_model=ChatSessionDetailOut)
async def get_chat_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = await get_session_with_messages(
        db, session_id=str(session_id), user_id=str(current_user.id)
    )
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在或无权限访问")

    # 单独查询消息（async SQLAlchemy 不支持懒加载关系）
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == str(session_id))
        .order_by(ChatMessage.created_at.asc())
    )
    messages = [
        ChatMessageOut.model_validate(m) for m in result.scalars().all()
    ]
    return ChatSessionDetailOut(
        id=session.id,
        project_id=session.project_id,
        user_id=session.user_id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=messages,
    )


@router.delete("/chat-sessions/{session_id}", status_code=204)
async def delete_chat_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == str(session_id),
            ChatSession.user_id == str(current_user.id),
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在或无权限访问")
    await db.delete(session)
    await db.commit()
    return None


@router.post("/chat-sessions/{session_id}/messages", response_model=ChatMessageOut)
async def create_chat_message(
    session_id: uuid.UUID,
    req: ChatMessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        assistant_message = await send_message(
            db,
            session_id=str(session_id),
            user_id=str(current_user.id),
            content=req.content,
        )
        return assistant_message
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
