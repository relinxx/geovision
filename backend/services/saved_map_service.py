"""
Saved map service for CRUD operations.
"""

from __future__ import annotations

import json
from datetime import datetime

from database import get_db
from schemas.saved_maps import (
    SavedMapCreate,
    SavedMapListItem,
    SavedMapListResponse,
    SavedMapResponse,
    SavedMapUpdate,
)


def _coerce_datetime(value) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    raise ValueError(f"Unsupported datetime value: {value!r}")


def _row_to_saved_map_list_item(row) -> SavedMapListItem:
    return SavedMapListItem(
        id=int(row["id"]),
        name=row["name"],
        description=row.get("description"),
        parcel_count=int(row["parcel_count"]),
        plan_count=int(row["plan_count"]),
        selected_plan_rank=(
            int(row["selected_plan_rank"]) if row.get("selected_plan_rank") is not None else None
        ),
        created_at=_coerce_datetime(row["created_at"]),
        updated_at=_coerce_datetime(row["updated_at"]),
    )


def _row_to_saved_map_response(row) -> SavedMapResponse:
    return SavedMapResponse(
        id=int(row["id"]),
        user_id=int(row["user_id"]),
        name=row["name"],
        description=row.get("description"),
        parcel_count=int(row["parcel_count"]),
        plan_count=int(row["plan_count"]),
        selected_plan_rank=(
            int(row["selected_plan_rank"]) if row.get("selected_plan_rank") is not None else None
        ),
        input_parcels=row["input_parcels"] if isinstance(row["input_parcels"], list) else [],
        optimization_result=row["optimization_result"]
        if isinstance(row["optimization_result"], dict)
        else {},
        created_at=_coerce_datetime(row["created_at"]),
        updated_at=_coerce_datetime(row["updated_at"]),
    )


class SavedMapService:
    """Service layer for user-scoped saved maps."""

    def create_saved_map(self, user_id: int, payload: SavedMapCreate) -> SavedMapResponse:
        input_parcels = payload.input_parcels if isinstance(payload.input_parcels, list) else []
        optimization_result = (
            payload.optimization_result if isinstance(payload.optimization_result, dict) else {}
        )
        plans = optimization_result.get("plans")
        parcel_count = len(input_parcels)
        plan_count = len(plans) if isinstance(plans, list) else 0

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO saved_maps (
                    user_id,
                    name,
                    description,
                    parcel_count,
                    plan_count,
                    selected_plan_rank,
                    input_parcels,
                    optimization_result
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
                RETURNING
                    id,
                    user_id,
                    name,
                    description,
                    parcel_count,
                    plan_count,
                    selected_plan_rank,
                    input_parcels,
                    optimization_result,
                    created_at,
                    updated_at
                """,
                (
                    user_id,
                    payload.name,
                    payload.description,
                    parcel_count,
                    plan_count,
                    payload.selected_plan_rank,
                    json.dumps(input_parcels),
                    json.dumps(optimization_result),
                ),
            )
            row = cursor.fetchone()
            conn.commit()
        return _row_to_saved_map_response(row)

    def list_saved_maps(self, user_id: int, limit: int, offset: int) -> SavedMapListResponse:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) AS total FROM saved_maps WHERE user_id = %s", (user_id,))
            count_row = cursor.fetchone() or {"total": 0}
            total = int(count_row.get("total", 0))

            cursor.execute(
                """
                SELECT
                    id,
                    name,
                    description,
                    parcel_count,
                    plan_count,
                    selected_plan_rank,
                    created_at,
                    updated_at
                FROM saved_maps
                WHERE user_id = %s
                ORDER BY updated_at DESC, id DESC
                LIMIT %s
                OFFSET %s
                """,
                (user_id, limit, offset),
            )
            rows = cursor.fetchall() or []

        return SavedMapListResponse(
            items=[_row_to_saved_map_list_item(row) for row in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    def get_saved_map(self, user_id: int, saved_map_id: int) -> SavedMapResponse | None:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    id,
                    user_id,
                    name,
                    description,
                    parcel_count,
                    plan_count,
                    selected_plan_rank,
                    input_parcels,
                    optimization_result,
                    created_at,
                    updated_at
                FROM saved_maps
                WHERE id = %s AND user_id = %s
                """,
                (saved_map_id, user_id),
            )
            row = cursor.fetchone()

        if not row:
            return None
        return _row_to_saved_map_response(row)

    def update_saved_map(
        self,
        user_id: int,
        saved_map_id: int,
        payload: SavedMapUpdate,
    ) -> SavedMapResponse | None:
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            return self.get_saved_map(user_id=user_id, saved_map_id=saved_map_id)

        set_clauses = []
        values = []
        for field in ("name", "description", "selected_plan_rank"):
            if field in updates:
                set_clauses.append(f"{field} = %s")
                values.append(updates[field])

        if not set_clauses:
            return self.get_saved_map(user_id=user_id, saved_map_id=saved_map_id)

        values.extend([saved_map_id, user_id])

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                UPDATE saved_maps
                SET {", ".join(set_clauses)}, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND user_id = %s
                RETURNING
                    id,
                    user_id,
                    name,
                    description,
                    parcel_count,
                    plan_count,
                    selected_plan_rank,
                    input_parcels,
                    optimization_result,
                    created_at,
                    updated_at
                """,
                tuple(values),
            )
            row = cursor.fetchone()
            conn.commit()

        if not row:
            return None
        return _row_to_saved_map_response(row)

    def delete_saved_map(self, user_id: int, saved_map_id: int) -> bool:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM saved_maps WHERE id = %s AND user_id = %s",
                (saved_map_id, user_id),
            )
            deleted = cursor.rowcount > 0
            conn.commit()
        return deleted


_saved_map_service: SavedMapService | None = None


def get_saved_map_service() -> SavedMapService:
    """Get or create saved map service singleton."""
    global _saved_map_service
    if _saved_map_service is None:
        _saved_map_service = SavedMapService()
    return _saved_map_service
