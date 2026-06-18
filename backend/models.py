"""
SQLAlchemy ORM models.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, DateTime, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB

class Base(DeclarativeBase):
    """Base class for ORM models."""


class User(Base):
    """Application user record."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SavedMap(Base):
    """
    A saved land-use planning map.

    This stores one optimization run, including:
    - original parcel GeoJSON features
    - generated plans
    - optimizer settings
    - objective names
    """

    __tablename__ = "saved_maps"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    parcel_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    plan_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    selected_plan_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)

    input_parcels: Mapped[dict] = mapped_column(JSONB, nullable=False)
    optimization_result: Mapped[dict] = mapped_column(JSONB, nullable=False)

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )