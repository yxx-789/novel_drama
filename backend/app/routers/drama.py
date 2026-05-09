import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.database import get_db
from app.models.project import DramaEpisode
from app.models.user import User
from app.routers.dependency import get_current_user
from app.schemas.drama import DramaEpisodeOut, ExportFormat
from app.services.drama.exporter import export_script
from app.services.project_service import get_project_by_id

router = APIRouter()


@router.get("/projects/{project_id}/drama-episodes", response_model=list[DramaEpisodeOut])
async def list_drama_episodes(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await get_project_by_id(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权限访问")
    result = await db.execute(
        select(DramaEpisode)
        .where(DramaEpisode.project_id == str(project_id))
        .order_by(DramaEpisode.episode_num)
    )
    return list(result.scalars().all())


@router.get("/drama/episodes/{episode_id}/export")
async def export_drama_episode(
    episode_id: uuid.UUID,
    format: ExportFormat = Query(..., description="导出格式: json, md, csv"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导出单集短剧脚本为 JSON / Markdown / CSV"""
    result = await db.execute(
        select(DramaEpisode).where(DramaEpisode.id == episode_id)
    )
    episode = result.scalar_one_or_none()
    if not episode:
        raise HTTPException(status_code=404, detail="剧集不存在")

    # 权限校验：通过 project_id 验证
    project = await get_project_by_id(db, uuid.UUID(episode.project_id), current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权限访问")

    if not episode.script_json:
        raise HTTPException(status_code=400, detail="该剧集尚未生成脚本，无法导出")

    content, media_type, filename = export_script(
        episode.script_json,
        format.value,
        filename=f"episode_{episode.episode_num:03d}",
    )

    return StreamingResponse(
        iter([content.encode("utf-8")]),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/drama/episodes/export/batch")
async def export_drama_episodes_batch(
    payload: dict,
    format: ExportFormat = Query(..., description="导出格式: json, md, csv"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量导出选中剧集脚本为合并文件"""
    episode_ids = payload.get("episode_ids", [])
    if not episode_ids:
        raise HTTPException(status_code=400, detail="未选择剧集")

    episode_ids_uuid = [uuid.UUID(ep_id) for ep_id in episode_ids]
    result = await db.execute(
        select(DramaEpisode).where(DramaEpisode.id.in_(episode_ids_uuid)).order_by(DramaEpisode.episode_num)
    )
    episodes = list(result.scalars().all())
    if not episodes:
        raise HTTPException(status_code=404, detail="未找到选中的剧集")

    project = await get_project_by_id(db, uuid.UUID(episodes[0].project_id), current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权限访问")

    # 过滤掉没有脚本的
    episodes = [ep for ep in episodes if ep.script_json]
    if not episodes:
        raise HTTPException(status_code=400, detail="选中的剧集尚未生成脚本")

    contents = []
    for ep in episodes:
        content, _, _ = export_script(ep.script_json, format.value, filename=f"episode_{ep.episode_num:03d}")
        contents.append(f"<!-- 第{ep.episode_num}集 {ep.title or ''} -->\n\n{content}")

    merged = "\n\n---\n\n".join(contents)
    ext = format.value
    if ext == "markdown":
        ext = "md"
    media_type_map = {
        "json": "application/json",
        "md": "text/markdown; charset=utf-8",
        "csv": "text/csv; charset=utf-8-sig",
    }

    return StreamingResponse(
        iter([merged.encode("utf-8")]),
        media_type=media_type_map.get(format.value, "text/plain"),
        headers={"Content-Disposition": f'attachment; filename="episodes_batch.{ext}"'},
    )

