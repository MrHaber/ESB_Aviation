from psycopg import AsyncConnection
from ..api.schemas import RequestLogResponse
from ..utils.helpers import get_current_timestamp
from loguru import logger
import json
import uuid
from datetime import datetime
from typing import Optional
from psycopg import AsyncConnection
from app.api.schemas import RequestLogResponse
from app.utils.helpers import get_current_timestamp, generate_request_id
from loguru import logger
from typing import List
import json

async def create_request_log(
    db: AsyncConnection,
    request_id: str,
    user_id: str,
    plugin_name: str,
    request_payload: dict,
    response_payload: dict,
    status: str,
    duration_ms: int
):
    query = """
    INSERT INTO request_logs (id, timestamp, user_id, plugin_name, request_payload, response_payload, status, duration_ms)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """
    timestamp = get_current_timestamp()
    try:
        async with db.cursor() as cur:
            await cur.execute(
                query,
                (
                    request_id,
                    timestamp,
                    user_id,
                    plugin_name,
                    json.dumps(request_payload),
                    json.dumps(response_payload),
                    status,
                    duration_ms
                )
            )
            await db.commit()
    except Exception as e:
        logger.error(f"Error logging request: {str(e)}")
        await db.rollback()

async def get_request_logs(
    db: AsyncConnection,
    limit: int = 10,
    offset: int = 0,
    plugin_name: Optional[str] = None,
    status: Optional[str] = None,
    start_timestamp: Optional[datetime] = None,
    end_timestamp: Optional[datetime] = None
) -> List[RequestLogResponse]:
    query = """
    SELECT id, timestamp, user_id, plugin_name, request_payload, response_payload, status, duration_ms
    FROM request_logs
    WHERE 1=1
    """
    params = []
    if plugin_name:
        query += " AND plugin_name = %s"
        params.append(plugin_name)
    if status:
        query += " AND status = %s"
        params.append(status)
    if start_timestamp:
        query += " AND timestamp >= %s"
        params.append(start_timestamp)
    if end_timestamp:
        query += " AND timestamp <= %s"
        params.append(end_timestamp)
    query += " LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    try:
        async with db.cursor() as cur:
            await cur.execute(query, tuple(params))
            rows = await cur.fetchall()
            return [
                RequestLogResponse(
                    id=str(row[0]),
                    timestamp=row[1],
                    user_id=row[2],
                    plugin_name=row[3],
                    request_payload=json.loads(row[4]) if isinstance(row[4], (str, bytes, bytearray)) else row[4], # дополнительная валидация входных данных
                    response_payload=json.loads(row[5]) if isinstance(row[5], (str, bytes, bytearray)) else row[5], # решил оставить так так как json объект может передаваться коряво
                    status=row[6],
                    duration_ms=row[7]
                )
                for row in rows
            ]
    except Exception as e:
        logger.error(f"Error retrieving logs: {str(e)}")
        return []