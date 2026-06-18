"""
Saved maps schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SavedMapCreate(BaseModel):
    """Schema for creating a saved map."""

    name: str = Field(..., min_length=1)
    description: str | None = None
    selected_plan_rank: int | None = None
    input_parcels: list[dict[str, Any]]
    optimization_result: dict[str, Any]


class SavedMapUpdate(BaseModel):
    """Schema for metadata-only saved map updates."""

    name: str | None = Field(default=None, min_length=1)
    description: str | None = None
    selected_plan_rank: int | None = None


class SavedMapListItem(BaseModel):
    """Metadata-only saved map list item."""

    id: int
    name: str
    description: str | None = None
    parcel_count: int
    plan_count: int
    selected_plan_rank: int | None = None
    created_at: datetime
    updated_at: datetime


class SavedMapResponse(BaseModel):
    """Full saved map response."""

    id: int
    user_id: int
    name: str
    description: str | None = None
    parcel_count: int
    plan_count: int
    selected_plan_rank: int | None = None
    input_parcels: list[dict[str, Any]]
    optimization_result: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class SavedMapListResponse(BaseModel):
    """Paginated saved map metadata response."""

    items: list[SavedMapListItem]
    total: int
    limit: int
    offset: int
