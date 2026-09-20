from datetime import datetime
from sqlalchemy import DateTime, String, Text, Integer, Boolean, Float, JSON, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SourceItem(Base):
    __tablename__ = 'source_items'
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(20))
    external_id: Mapped[str] = mapped_column(String(128))
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint('source', 'external_id'),)


class Decision(Base):
    __tablename__ = 'decisions'
    id: Mapped[int] = mapped_column(primary_key=True)
    source_item_id: Mapped[int] = mapped_column(Integer)
    classification: Mapped[str] = mapped_column(String(20))
    source_confidence: Mapped[float] = mapped_column(Float)
    ai_confidence: Mapped[float] = mapped_column(Float)
    payload: Mapped[dict] = mapped_column(JSON)
    fingerprint: Mapped[str] = mapped_column(String(128), unique=True)
    executed: Mapped[bool] = mapped_column(Boolean, default=False)
    execution_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
