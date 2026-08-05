from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inspiration import HotTopic
from app.models.project import Project, ProjectAsset


async def get_hot_notes(
    db: AsyncSession,
    category: Optional[str] = None,
    keyword: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """读最近一批 hot_topics，按点赞降序。keyword 对 title/summary 做模糊过滤（只搜已采集数据）。"""
    latest = await db.execute(
        select(HotTopic.fetched_at).order_by(HotTopic.fetched_at.desc()).limit(1)
    )
    latest_ts = latest.scalar_one_or_none()

    stmt = select(HotTopic).order_by(HotTopic.likes.desc()).limit(limit)
    if latest_ts is not None:
        stmt = stmt.where(HotTopic.fetched_at == latest_ts)
    if category:
        stmt = stmt.where(HotTopic.category == category)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where((HotTopic.title.ilike(like)) | (HotTopic.summary.ilike(like)))

    result = await db.execute(stmt)
    notes = result.scalars().all()
    return [
        {
            "note_id": n.note_id,
            "title": n.title,
            "summary": n.summary,
            "likes": n.likes,
            "collects": n.collects,
            "url": n.url,
            "author": n.author,
            "fetched_at": n.fetched_at,
        }
        for n in notes
    ]


async def import_inspiration(db: AsyncSession, project: Project, note: dict) -> Project:
    """设项目主题 + 存 inspiration 资产。幂等：重复导入同一灵感覆盖 asset。"""
    if note.get("title"):
        project.topic = note["title"]
        await db.flush()

    content = {
        "note_id": note.get("note_id"),
        "title": note.get("title"),
        "summary": note.get("summary"),
        "likes": note.get("likes"),
        "url": note.get("url"),
        "author": note.get("author"),
        "tags": note.get("tags", []),
    }
    result = await db.execute(
        select(ProjectAsset).where(
            ProjectAsset.project_id == str(project.id),
            ProjectAsset.asset_type == "inspiration",
        )
    )
    asset = result.scalar_one_or_none()
    if asset:
        asset.content_json = content
        asset.version += 1
    else:
        asset = ProjectAsset(
            project_id=str(project.id),
            asset_type="inspiration",
            content_json=content,
        )
        db.add(asset)
    await db.commit()
    await db.refresh(project)
    return project


async def build_inspiration_guidance(db: AsyncSession, project_id: str) -> str:
    """读取项目已导入的灵感资产，格式化为生成 prompt 的创作引导。"""
    result = await db.execute(
        select(ProjectAsset).where(
            ProjectAsset.project_id == project_id,
            ProjectAsset.asset_type == "inspiration",
        )
    )
    asset = result.scalar_one_or_none()
    if not asset or not asset.content_json:
        return ""
    c = asset.content_json
    lines = [f"- 标题：{c.get('title', '')}"]
    if c.get("summary"):
        lines.append(f"- 摘要：{c['summary']}")
    if c.get("tags"):
        lines.append(f"- 标签：{'、'.join(c['tags'])}")
    if c.get("likes"):
        lines.append(f"- 热度：{c['likes']} 赞")
    return "\n".join(lines)
