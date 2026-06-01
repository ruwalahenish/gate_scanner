from uuid import UUID
import asyncpg


async def create_scan(conn: asyncpg.Connection, scan_id: UUID, mode: str) -> None:
    await conn.execute(
        "INSERT INTO scans(id, mode, status) VALUES($1, $2, 'pending')",
        scan_id, mode,
    )


async def update_scan_status(
    conn: asyncpg.Connection,
    scan_id: UUID,
    status: str,
    *,
    signals_found: int = 0,
    passed_filter: int = 0,
    universe_size: int = 0,
    duration_sec: float = 0.0,
    error_message: str | None = None,
) -> None:
    await conn.execute(
        """UPDATE scans SET
            status=$2, completed_at=NOW(),
            signals_found=$3, passed_filter=$4,
            universe_size=$5, duration_sec=$6, error_message=$7
           WHERE id=$1""",
        scan_id, status, signals_found, passed_filter,
        universe_size, duration_sec, error_message,
    )


async def get_scan(conn: asyncpg.Connection, scan_id: UUID) -> asyncpg.Record | None:
    return await conn.fetchrow("SELECT * FROM scans WHERE id=$1", scan_id)


async def list_scans(
    conn: asyncpg.Connection, limit: int = 20, offset: int = 0
) -> list[asyncpg.Record]:
    return await conn.fetch(
        "SELECT * FROM scans ORDER BY triggered_at DESC LIMIT $1 OFFSET $2",
        limit, offset,
    )


async def has_running_scan(conn: asyncpg.Connection, within_seconds: int = 600) -> bool:
    """Return True only if a scan started recently is still pending/running."""
    row = await conn.fetchrow(
        """SELECT 1 FROM scans
           WHERE status IN ('pending', 'running')
             AND triggered_at > NOW() - ($1 || ' seconds')::INTERVAL
           LIMIT 1""",
        str(within_seconds),
    )
    return row is not None


async def get_latest_done_scan_id(conn: asyncpg.Connection) -> UUID | None:
    row = await conn.fetchrow(
        "SELECT id FROM scans WHERE status='done' ORDER BY triggered_at DESC LIMIT 1"
    )
    return row["id"] if row else None
