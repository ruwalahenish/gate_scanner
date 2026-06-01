from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
import asyncpg

from app.dependencies import db_conn
from app.models.alert import CreateAlertRequest, AlertModel, ALERT_TYPES
from app.queries.alerts import (
    create_alert, get_alerts, dismiss_alert, delete_alert
)

router = APIRouter(tags=["alerts"])


@router.get("")
async def list_alerts(
    status: str | None = Query(None, regex="^(active|triggered|dismissed|expired)$"),
    conn: asyncpg.Connection = Depends(db_conn),
):
    rows = await get_alerts(conn, status)
    return [_serialize(r) for r in rows]


@router.post("")
async def create_new_alert(
    body: CreateAlertRequest,
    conn: asyncpg.Connection = Depends(db_conn),
):
    if body.alert_type not in ALERT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown alert_type. Valid: {sorted(ALERT_TYPES)}"
        )
    alert_id = await create_alert(
        conn,
        symbol=body.symbol.upper(),
        alert_type=body.alert_type,
        threshold_value=body.threshold_value,
        timeframe=body.timeframe,
        message=body.message,
        notify_via=body.notify_via,
    )
    return {"alert_id": str(alert_id), "status": "active"}


@router.post("/{alert_id}/dismiss")
async def dismiss(
    alert_id: UUID,
    conn: asyncpg.Connection = Depends(db_conn),
):
    await dismiss_alert(conn, alert_id)
    return {"dismissed": True}


@router.delete("/{alert_id}")
async def delete(
    alert_id: UUID,
    conn: asyncpg.Connection = Depends(db_conn),
):
    await delete_alert(conn, alert_id)
    return {"deleted": True}


def _serialize(row) -> dict:
    d = dict(row)
    for k, v in d.items():
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
        elif type(v).__name__ == "UUID":
            d[k] = str(v)
        elif type(v).__name__ == "Decimal":
            d[k] = float(v)
    return d
