import sqlalchemy as sa
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class Project(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    topic: Mapped[str | None] = mapped_column(Text)
    genre: Mapped[str | None] = mapped_column(String(100))
    num_chapters: Mapped[int] = mapped_column(Integer, default=0)
    word_number: Mapped[int] = mapped_column(Integer, default=0)
    story_shape: Mapped[str] = mapped_column(String(20), nullable=False)
    total_chapters_target: Mapped[int | None] = mapped_column(Integer, nullable=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    writing_config: Mapped[dict | None] = mapped_column(JSONB)

    chapters: Mapped[list["Chapter"]] = relationship("Chapter", back_populates="project", cascade="all, delete-orphan")
    assets: Mapped[list["ProjectAsset"]] = relationship("ProjectAsset", back_populates="project", cascade="all, delete-orphan")


class Chapter(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "chapters"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    chapter_num: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))
    outline: Mapped[str | None] = mapped_column(Text)
    draft: Mapped[str | None] = mapped_column(Text)
    finalized_text: Mapped[str | None] = mapped_column(Text)
    actual_summary_json: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    version: Mapped[int] = mapped_column(Integer, default=1)

    project: Mapped["Project"] = relationship("Project", back_populates="chapters")

    __table_args__ = (
        {"sqlite_autoincrement": True},
    )


class ProjectAsset(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "project_assets"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content_text: Mapped[str | None] = mapped_column(Text)
    content_json: Mapped[dict | None] = mapped_column(JSONB)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))

    project: Mapped["Project"] = relationship("Project", back_populates="assets")


class AssetVersion(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "asset_versions"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(20), nullable=False, default="generate")
    guidance: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))

    __table_args__ = (
        sa.UniqueConstraint("project_id", "asset_type", "version", name="uq_asset_versions_project_type_version"),
        {"sqlite_autoincrement": True},
    )


class Task(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "tasks"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    params: Mapped[dict | None] = mapped_column(JSONB)
    result: Mapped[dict | None] = mapped_column(JSONB)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    error_msg: Mapped[str | None] = mapped_column(Text)


class DramaEpisode(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "drama_episodes"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    episode_num: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))
    source_chapters: Mapped[str | None] = mapped_column(String(255))
    outline_json: Mapped[dict | None] = mapped_column(JSONB)
    script_json: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), default="pending")

    __table_args__ = (
        {"sqlite_autoincrement": True},
    )
