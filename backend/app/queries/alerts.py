from uuid import UUID, uuid4
import asyncpg


async def create_alert(
    conn: asyncpg.Connection,
    symbol: str,
    alert_type: str,
    threshold_value: float | None = None,
    timeframe: str | None = None,
    message: str | None = None,
    notify_via: list[str] | None = None,
) -> UUID:
    alert_id = uuid4()
    await conn.execute(
        """INSERT INTO alerts
           (id, symbol, alert_type, threshold_value, timeframe, message, notify_via)
           VALUES($1,$2,$3,$4,$5,$6,$7)""",
        alert_id, symbol, alert_type, threshold_value, timeframe,
        message, notify_via or ["web"],
    )
    return alert_id


async def get_alerts(
    conn: asyncpg.Connection, status: str | None = None
) -> list[asyncpg.Record]:
    if status:
        return await conn.fetch(
            "SELECT * FROM alerts WHERE status=$1 ORDER BY created_at DESC", status
        )
    return await conn.fetch("SELECT * FROM alerts ORDER BY created_at DESC")


async def get_active_alerts(conn: asyncpg.Connection) -> list[asyncpg.Record]:
    return await conn.fetch(
        "SELECT * FROM alerts WHERE status='active'"
    )


async def trigger_alert(
    conn: asyncpg.Connection, alert_id: UUID, triggered_price: float
) -> None:
    await conn.execute(
        """UPDATE alerts SET status='triggered', triggered_at=NOW(), triggered_price=$2
           WHERE id=$1""",
        alert_id, triggered_price,
    )


async def dismiss_alert(conn: asyncpg.Connection, alert_id: UUID) -> None:
    await conn.execute(
        "UPDATE alerts SET status='dismissed' WHERE id=$1", alert_id
    )


async def delete_alert(conn: asyncpg.Connection, alert_id: UUID) -> None:
    await conn.execute("DELETE FROM alerts WHERE id=$1", alert_id)
