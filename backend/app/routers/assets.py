import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.database import get_db
from app.models.project import ProjectAsset
from app.models.user import User
from app.routers.dependency import get_current_user
from app.schemas.drama import ExportFormat
from app.services.project_service import get_project_by_id

router = APIRouter()

ASSET_TYPES = {"architecture", "directory", "characters", "settings", "drama_plan", "world_state"}


@router.get("/projects/{project_id}/assets/{asset_type}/export")
async def export_asset(
    project_id: uuid.UUID,
    asset_type: str,
    format: ExportFormat = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if asset_type not in ASSET_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的资产类型: {asset_type}")
    project = await get_project_by_id(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权限访问")
    result = await db.execute(
        select(ProjectAsset).where(
            ProjectAsset.project_id == str(project_id),
            ProjectAsset.asset_type == asset_type,
        )
    )
    asset = result.scalar_one_or_none()
    if not asset or not asset.content_text:
        raise HTTPException(status_code=404, detail="该内容尚未生成")

    content = asset.content_text
    if format.value == "json":
        content = f'{{"asset_type": "{asset_type}", "content": {repr(content)[1:-1]}}}'
        media_type = "application/json"
        ext = "json"
    else:
        media_type = "text/markdown; charset=utf-8"
        ext = "md"

    return StreamingResponse(
        iter([content.encode("utf-8")]),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{asset_type}.{ext}"'},
    )


@router.get("/projects/{project_id}/assets/{asset_type}")
async def get_asset(
    project_id: uuid.UUID,
    asset_type: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if asset_type not in ASSET_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的资产类型: {asset_type}")
    project = await get_project_by_id(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权限访问")
    result = await db.execute(
        select(ProjectAsset).where(
            ProjectAsset.project_id == str(project_id),
            ProjectAsset.asset_type == asset_type,
        )
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="该内容尚未生成")
    return {
        "id": asset.id,
        "project_id": asset.project_id,
        "asset_type": asset.asset_type,
        "content_text": asset.content_text,
        "content_json": asset.content_json,
        "version": asset.version,
        "updated_at": asset.updated_at,
    }


@router.put("/projects/{project_id}/assets/{asset_type}")
async def upsert_asset(
    project_id: uuid.UUID,
    asset_type: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if asset_type not in ASSET_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的资产类型: {asset_type}")
    project = await get_project_by_id(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权限访问")

    result = await db.execute(
        select(ProjectAsset).where(
            ProjectAsset.project_id == str(project_id),
            ProjectAsset.asset_type == asset_type,
        )
    )
    asset = result.scalar_one_or_none()
    content_text = payload.get("content_text")
    content_json = payload.get("content_json")

    if asset:
        asset.content_text = content_text
        asset.content_json = content_json
        asset.version += 1
        asset.updated_by = str(current_user.id)
    else:
        asset = ProjectAsset(
            project_id=str(project_id),
            asset_type=asset_type,
            content_text=content_text,
            content_json=content_json,
            updated_by=str(current_user.id),
        )
        db.add(asset)

    await db.commit()
    await db.refresh(asset)
    return {
        "id": asset.id,
        "project_id": asset.project_id,
        "asset_type": asset.asset_type,
        "content_text": asset.content_text,
        "content_json": asset.content_json,
        "version": asset.version,
        "updated_at": asset.updated_at,
    }
