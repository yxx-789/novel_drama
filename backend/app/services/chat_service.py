import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.generator.llm_adapter import create_llm_adapter
from app.models.chat import ChatMessage, ChatSession
from app.models.project import ProjectAsset

SYSTEM_PROMPT_TEMPLATE = """你是一位专业的小说创作顾问。你的职责是帮助用户构思、分析和讨论创作思路，但你绝不替用户直接生成小说正文、章节内容或完整剧本。

当前项目信息（供你参考上下文）：

【世界观与架构】
{architecture}

【章节目录】
{directory}

你可以做：
- 分析剧情结构和节奏，指出潜在问题
- 提供角色发展方向和动机建议
- 讨论世界观设定是否合理、自洽
- 给出写作技巧、灵感启发和参考案例
- 帮助梳理故事线索、伏笔和悬念安排
- 对已有大纲提出优化建议

你绝不做：
- 直接写出小说章节正文
- 生成分镜头剧本或完整场景描写
- 替用户写大段对话或叙述性文字
- 输出可直接当作成品的创作内容
- 执行任何"帮我把这段写完"之类的请求

回答风格：简洁、有建设性、以提问和引导为主，激发用户自己的创作能力。如果用户要求你生成内容，请温和地拒绝并引导回讨论和构思。"""


async def create_session(
    db: AsyncSession,
    user_id: str,
    project_id: str | None = None,
    title: str | None = None,
) -> ChatSession:
    session = ChatSession(
        user_id=user_id,
        project_id=project_id,
        title=title or "新会话",
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def list_sessions(
    db: AsyncSession,
    user_id: str,
    project_id: str | None = None,
) -> list[ChatSession]:
    stmt = select(ChatSession).where(ChatSession.user_id == user_id)
    if project_id:
        stmt = stmt.where(ChatSession.project_id == project_id)
    stmt = stmt.order_by(ChatSession.updated_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_session_with_messages(
    db: AsyncSession,
    session_id: str,
    user_id: str,
) -> ChatSession | None:
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def _get_project_context(
    db: AsyncSession,
    project_id: str | None,
) -> tuple[str, str]:
    if not project_id:
        return "", ""

    result = await db.execute(
        select(ProjectAsset).where(
            ProjectAsset.project_id == project_id,
            ProjectAsset.asset_type.in_(["architecture", "directory"]),
        )
    )
    assets = result.scalars().all()

    architecture = ""
    directory = ""
    for asset in assets:
        if asset.asset_type == "architecture":
            architecture = asset.content_text or ""
        elif asset.asset_type == "directory":
            directory = asset.content_text or ""

    return architecture, directory


async def send_message(
    db: AsyncSession,
    session_id: str,
    user_id: str,
    content: str,
) -> ChatMessage:
    # 校验会话归属
    session = await get_session_with_messages(db, session_id, user_id)
    if not session:
        raise ValueError("会话不存在或无权限访问")

    # 保存用户消息
    user_message = ChatMessage(
        session_id=session_id,
        role="user",
        content=content,
    )
    db.add(user_message)
    await db.commit()

    # 获取历史消息（最近 20 条，避免 token 超限）
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
    )
    all_messages = result.scalars().all()
    recent_messages = all_messages[-20:]

    # 获取项目上下文
    architecture, directory = await _get_project_context(db, session.project_id)

    # 构建 system prompt
    system_content = SYSTEM_PROMPT_TEMPLATE.format(
        architecture=architecture or "（尚未生成）",
        directory=directory or "（尚未生成）",
    )

    # 构建 messages 列表
    messages = [{"role": "system", "content": system_content}]
    for msg in recent_messages:
        messages.append({"role": msg.role, "content": msg.content})

    # 调用 LLM
    adapter = create_llm_adapter(
        interface_format=settings.LLM_INTERFACE_FORMAT,
        base_url=settings.LLM_BASE_URL,
        model_name=settings.LLM_MODEL,
        api_key=settings.LLM_API_KEY,
        temperature=0.7,
        max_tokens=4096,
        timeout=settings.LLM_TIMEOUT,
    )
    assistant_content = await adapter.invoke_messages(messages)

    # 保存 AI 回复
    assistant_message = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=assistant_content,
        model_name=settings.LLM_MODEL,
    )
    db.add(assistant_message)
    await db.commit()
    await db.refresh(assistant_message)

    # 如果会话还没有标题，用第一条用户消息作为标题
    if not session.title or session.title == "新会话":
        session.title = content[:30] + "..." if len(content) > 30 else content
        await db.commit()

    return assistant_message
