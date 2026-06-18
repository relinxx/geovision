"""
Saved maps router.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from routers.auth import get_current_user
from schemas.auth import UserResponse
from schemas.saved_maps import (
    SavedMapCreate,
    SavedMapListResponse,
    SavedMapResponse,
    SavedMapUpdate,
)
from services.saved_map_service import SavedMapService, get_saved_map_service

router = APIRouter(prefix="/saved-maps", tags=["saved-maps"])


@router.post("", response_model=SavedMapResponse, status_code=status.HTTP_201_CREATED)
async def create_saved_map(
    payload: SavedMapCreate,
    current_user: UserResponse = Depends(get_current_user),
    service: SavedMapService = Depends(get_saved_map_service),
):
    return service.create_saved_map(user_id=current_user.id, payload=payload)


@router.get("", response_model=SavedMapListResponse)
async def list_saved_maps(
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: UserResponse = Depends(get_current_user),
    service: SavedMapService = Depends(get_saved_map_service),
):
    return service.list_saved_maps(user_id=current_user.id, limit=limit, offset=offset)


@router.get("/{saved_map_id}", response_model=SavedMapResponse)
async def get_saved_map(
    saved_map_id: int,
    current_user: UserResponse = Depends(get_current_user),
    service: SavedMapService = Depends(get_saved_map_service),
):
    saved_map = service.get_saved_map(user_id=current_user.id, saved_map_id=saved_map_id)
    if not saved_map:
        raise HTTPException(status_code=404, detail="Saved map not found")
    return saved_map


@router.patch("/{saved_map_id}", response_model=SavedMapResponse)
async def update_saved_map(
    saved_map_id: int,
    payload: SavedMapUpdate,
    current_user: UserResponse = Depends(get_current_user),
    service: SavedMapService = Depends(get_saved_map_service),
):
    updated = service.update_saved_map(
        user_id=current_user.id,
        saved_map_id=saved_map_id,
        payload=payload,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Saved map not found")
    return updated


@router.delete("/{saved_map_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_map(
    saved_map_id: int,
    current_user: UserResponse = Depends(get_current_user),
    service: SavedMapService = Depends(get_saved_map_service),
):
    deleted = service.delete_saved_map(user_id=current_user.id, saved_map_id=saved_map_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Saved map not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
