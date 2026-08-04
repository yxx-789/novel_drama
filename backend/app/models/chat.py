from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class ChatSession(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "chat_sessions"

    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )


class ChatMessage(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "chat_messages"

    session_id: Mapped[str] = mapped_column(ForeignKey("chat_sessions.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(nullable=True)
    meta_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    session: Mapped["ChatSession"] = relationship("ChatSession", back_populates="messages")
