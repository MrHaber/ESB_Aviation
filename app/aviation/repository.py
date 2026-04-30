from contextlib import contextmanager
import json
import sqlite3
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional

from .models import AviationMessage, RoutingDecision


SCHEMA = """
CREATE TABLE IF NOT EXISTS aviation_messages (
    message_id TEXT PRIMARY KEY,
    message_type TEXT NOT NULL,
    priority TEXT NOT NULL,
    origin_airport TEXT NOT NULL,
    destination_airport TEXT NOT NULL,
    flight_number TEXT NOT NULL,
    operator TEXT NOT NULL,
    received_at TEXT NOT NULL,
    aircraft_registration TEXT,
    payload TEXT NOT NULL,
    context TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_aviation_messages_type
    ON aviation_messages(message_type);
CREATE INDEX IF NOT EXISTS idx_aviation_messages_priority
    ON aviation_messages(priority);
CREATE INDEX IF NOT EXISTS idx_aviation_messages_airports
    ON aviation_messages(origin_airport, destination_airport);

CREATE TABLE IF NOT EXISTS aviation_routing_decisions (
    message_id TEXT PRIMARY KEY,
    route_key TEXT NOT NULL,
    destinations TEXT NOT NULL,
    priority_channel TEXT NOT NULL,
    reasons TEXT NOT NULL,
    ttl_seconds INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(message_id) REFERENCES aviation_messages(message_id)
);
"""


class AviationMessageRepository:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(SCHEMA)
            connection.commit()

    def replace_messages(self, messages: Iterable[AviationMessage]) -> int:
        self.initialize()
        rows = [self._message_row(message) for message in messages]
        with self._connect() as connection:
            connection.execute("DELETE FROM aviation_routing_decisions")
            connection.execute("DELETE FROM aviation_messages")
            connection.executemany(
                """
                INSERT INTO aviation_messages (
                    message_id, message_type, priority, origin_airport, destination_airport,
                    flight_number, operator, received_at, aircraft_registration, payload, context
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            connection.commit()
        return len(rows)

    def add_message(self, message: AviationMessage) -> AviationMessage:
        self.initialize()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO aviation_messages (
                    message_id, message_type, priority, origin_airport, destination_airport,
                    flight_number, operator, received_at, aircraft_registration, payload, context
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._message_row(message),
            )
            connection.commit()
        return message

    def update_message(self, message_id: str, message: AviationMessage) -> Optional[AviationMessage]:
        self.initialize()
        if self.get_message(message_id) is None:
            return None

        normalized = AviationMessage.from_dict({**message.to_dict(), "message_id": message_id})
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE aviation_messages
                SET message_type = ?,
                    priority = ?,
                    origin_airport = ?,
                    destination_airport = ?,
                    flight_number = ?,
                    operator = ?,
                    received_at = ?,
                    aircraft_registration = ?,
                    payload = ?,
                    context = ?
                WHERE message_id = ?
                """,
                (
                    normalized.message_type,
                    normalized.priority,
                    normalized.origin_airport,
                    normalized.destination_airport,
                    normalized.flight_number,
                    normalized.operator,
                    normalized.received_at.isoformat(),
                    normalized.aircraft_registration,
                    json.dumps(normalized.payload, ensure_ascii=True),
                    json.dumps(normalized.context, ensure_ascii=True),
                    message_id,
                ),
            )
            connection.commit()
        return normalized

    def list_messages(
        self,
        limit: int = 50,
        offset: int = 0,
        message_type: Optional[str] = None,
        priority: Optional[str] = None,
        airport: Optional[str] = None,
    ) -> List[AviationMessage]:
        self.initialize()
        query = "SELECT * FROM aviation_messages WHERE 1=1"
        params: list[object] = []

        if message_type:
            query += " AND message_type = ?"
            params.append(message_type.upper())
        if priority:
            query += " AND priority = ?"
            params.append(priority.upper())
        if airport:
            query += " AND (origin_airport = ? OR destination_airport = ?)"
            params.extend([airport.upper(), airport.upper()])

        query += " ORDER BY received_at ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._message_from_row(row) for row in rows]

    def get_message(self, message_id: str) -> Optional[AviationMessage]:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM aviation_messages WHERE message_id = ?",
                (message_id,),
            ).fetchone()
        if row is None:
            return None
        return self._message_from_row(row)

    def save_routing_decision(self, decision: RoutingDecision) -> None:
        self.initialize()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO aviation_routing_decisions (
                    message_id, route_key, destinations, priority_channel, reasons, ttl_seconds
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    decision.message_id,
                    decision.route_key,
                    json.dumps(decision.destinations),
                    decision.priority_channel,
                    json.dumps(decision.reasons),
                    decision.ttl_seconds,
                ),
            )
            connection.commit()

    def list_routing_decisions(self, limit: int = 50) -> List[Dict[str, object]]:
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT message_id, route_key, destinations, priority_channel, reasons, ttl_seconds, created_at
                FROM aviation_routing_decisions
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            {
                "message_id": row["message_id"],
                "route_key": row["route_key"],
                "destinations": json.loads(row["destinations"]),
                "priority_channel": row["priority_channel"],
                "reasons": json.loads(row["reasons"]),
                "ttl_seconds": row["ttl_seconds"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def count_messages(self) -> int:
        self.initialize()
        with self._connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM aviation_messages").fetchone()[0])

    def overview(self) -> Dict[str, object]:
        self.initialize()
        with self._connect() as connection:
            total = int(connection.execute("SELECT COUNT(*) FROM aviation_messages").fetchone()[0])
            routed = int(connection.execute("SELECT COUNT(*) FROM aviation_routing_decisions").fetchone()[0])
            types = connection.execute(
                "SELECT message_type, COUNT(*) AS count FROM aviation_messages GROUP BY message_type ORDER BY count DESC"
            ).fetchall()
            priorities = connection.execute(
                "SELECT priority, COUNT(*) AS count FROM aviation_messages GROUP BY priority ORDER BY count DESC"
            ).fetchall()
            sources = connection.execute("SELECT context FROM aviation_messages").fetchall()

        source_counts: Dict[str, int] = {}
        for row in sources:
            context = json.loads(row["context"])
            source = str(context.get("source_system") or "unknown")
            source_counts[source] = source_counts.get(source, 0) + 1

        return {
            "total_messages": total,
            "routed_messages": routed,
            "message_types": {row["message_type"]: row["count"] for row in types},
            "priorities": {row["priority"]: row["count"] for row in priorities},
            "source_systems": source_counts,
        }

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    def _message_row(self, message: AviationMessage) -> tuple:
        return (
            message.message_id,
            message.message_type,
            message.priority,
            message.origin_airport,
            message.destination_airport,
            message.flight_number,
            message.operator,
            message.received_at.isoformat(),
            message.aircraft_registration,
            json.dumps(message.payload, ensure_ascii=True),
            json.dumps(message.context, ensure_ascii=True),
        )

    def _message_from_row(self, row: sqlite3.Row) -> AviationMessage:
        return AviationMessage.from_dict(
            {
                "message_id": row["message_id"],
                "message_type": row["message_type"],
                "priority": row["priority"],
                "origin_airport": row["origin_airport"],
                "destination_airport": row["destination_airport"],
                "flight_number": row["flight_number"],
                "operator": row["operator"],
                "received_at": row["received_at"],
                "aircraft_registration": row["aircraft_registration"],
                "payload": json.loads(row["payload"]),
                "context": json.loads(row["context"]),
            }
        )
