from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class HotTopic(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "hot_topics"
    __table_args__ = (
        UniqueConstraint("note_id", name="uq_hot_topics_note_id"),
    )

    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    note_id: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    collects: Mapped[int] = mapped_column(Integer, default=0)
    shares: Mapped[int] = mapped_column(Integer, default=0)
    url: Mapped[str | None] = mapped_column(String(512))
    author: Mapped[str | None] = mapped_column(String(128))
    source: Mapped[str] = mapped_column(String(32), default="xiaohongshu")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
