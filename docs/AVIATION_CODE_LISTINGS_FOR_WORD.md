# Листинги кода авиационного контура ESB Aviation

Документ подготовлен для вставки в пояснительную записку дипломного проекта или для передачи нейросети, которая будет визуализировать архитектуру и интерфейс.

В листинги включены только ключевые фрагменты авиационного контура и пользовательского интерфейса `app/templates/index.html`.

## Листинг 1. Доменная модель авиационного сообщения

Файл: `app/aviation/models.py`

Назначение: описание типов авиационных сообщений, приоритетов, структуры сообщения и результата маршрутизации.

```python
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class AviationMessageType(str, Enum):
    FPL = "FPL"
    DLA = "DLA"
    CNL = "CNL"
    CHG = "CHG"
    MVT = "MVT"
    LDM = "LDM"
    CPM = "CPM"
    NOTAM = "NOTAM"
    METAR = "METAR"
    TAF = "TAF"
    SIGMET = "SIGMET"
    SLOT = "SLOT"
    PAXLST = "PAXLST"
    BAG = "BAG"
    MAINT = "MAINT"
    TECHLOG = "TECHLOG"
    SECURITY = "SECURITY"
    AFTN = "AFTN"


class MessagePriority(str, Enum):
    NORMAL = "NORMAL"
    URGENT = "URGENT"
    CRITICAL = "CRITICAL"
    DISTRESS = "DISTRESS"


@dataclass(frozen=True)
class AviationMessage:
    message_id: str
    message_type: str
    priority: str
    origin_airport: str
    destination_airport: str
    flight_number: str
    operator: str
    received_at: datetime
    payload: Dict[str, Any]
    aircraft_registration: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "AviationMessage":
        received_at = value.get("received_at")
        if isinstance(received_at, str):
            received_at = datetime.fromisoformat(received_at.replace("Z", "+00:00"))
        if received_at is None:
            received_at = datetime.now(timezone.utc)

        return cls(
            message_id=str(value["message_id"]),
            message_type=str(value["message_type"]).upper(),
            priority=str(value.get("priority", MessagePriority.NORMAL.value)).upper(),
            origin_airport=str(value.get("origin_airport", "")).upper(),
            destination_airport=str(value.get("destination_airport", "")).upper(),
            flight_number=str(value.get("flight_number", "")),
            operator=str(value.get("operator", "")),
            received_at=received_at,
            payload=dict(value.get("payload", {})),
            aircraft_registration=value.get("aircraft_registration"),
            context=dict(value.get("context", {})),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "message_type": self.message_type,
            "priority": self.priority,
            "origin_airport": self.origin_airport,
            "destination_airport": self.destination_airport,
            "flight_number": self.flight_number,
            "operator": self.operator,
            "received_at": self.received_at.isoformat(),
            "payload": self.payload,
            "aircraft_registration": self.aircraft_registration,
            "context": self.context,
        }


@dataclass(frozen=True)
class RoutingDecision:
    message_id: str
    route_key: str
    destinations: List[str]
    priority_channel: str
    reasons: List[str]
    ttl_seconds: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "route_key": self.route_key,
            "destinations": self.destinations,
            "priority_channel": self.priority_channel,
            "reasons": self.reasons,
            "ttl_seconds": self.ttl_seconds,
        }
```

## Листинг 2. Правила контекстной маршрутизации

Файл: `app/aviation/routing.py`

Назначение: построение маршрута доставки авиационного сообщения с учетом типа, аэропортов, фазы рейса, погоды, безопасности, приоритета и регуляторной зоны.

```python
from typing import Dict, Iterable, List, Set

from .models import AviationMessage, MessagePriority, RoutingDecision


HUB_AIRPORTS = {"UUDD", "UUEE", "ULLI", "URSS"}
SAFETY_EVENTS = {"emergency", "diversion", "bird_strike", "runway_incursion"}
SECURITY_EVENTS = {"security_alert", "unruly_passenger", "screening_match"}


BASE_DESTINATIONS: Dict[str, List[str]] = {
    "FPL": ["flight_dispatch", "atc_gateway", "airport_operations"],
    "DLA": ["flight_dispatch", "atc_gateway", "passenger_service"],
    "CNL": ["flight_dispatch", "atc_gateway", "passenger_service"],
    "CHG": ["flight_dispatch", "atc_gateway", "airport_operations"],
    "SLOT": ["slot_coordination", "flight_dispatch", "airport_operations"],
    "MVT": ["flight_dispatch", "airport_operations", "ground_handling"],
    "LDM": ["load_control", "ground_handling", "airport_operations"],
    "CPM": ["load_control", "cargo_handling", "ground_handling"],
    "PAXLST": ["border_control", "passenger_service", "airport_operations"],
    "BAG": ["baggage_reconciliation", "ground_handling"],
    "NOTAM": ["flight_dispatch", "airport_operations", "safety_control"],
    "METAR": ["meteorology", "flight_dispatch"],
    "TAF": ["meteorology", "flight_dispatch"],
    "SIGMET": ["meteorology", "flight_dispatch", "safety_control"],
    "MAINT": ["maintenance_control", "flight_dispatch"],
    "TECHLOG": ["maintenance_control", "flight_dispatch"],
    "SECURITY": ["security_control", "airport_operations"],
    "AFTN": ["message_triage", "flight_dispatch"],
}


class ContextAwareAviationRouter:

    def route(self, message: AviationMessage) -> RoutingDecision:
        message_type = message.message_type.upper()
        destinations: Set[str] = set(BASE_DESTINATIONS.get(message_type, ["message_triage"]))
        reasons = [f"type:{message_type}"]

        self._apply_airport_context(message, destinations, reasons)
        self._apply_operational_context(message, destinations, reasons)
        self._apply_weather_context(message, destinations, reasons)
        self._apply_priority_context(message, destinations, reasons)
        self._apply_regulatory_context(message, destinations, reasons)

        priority_channel = self._priority_channel(message)
        route_key = self._route_key(message, priority_channel)
        ttl_seconds = self._ttl_seconds(priority_channel, message_type)

        return RoutingDecision(
            message_id=message.message_id,
            route_key=route_key,
            destinations=sorted(destinations),
            priority_channel=priority_channel,
            reasons=reasons,
            ttl_seconds=ttl_seconds,
        )

    def route_many(self, messages: Iterable[AviationMessage]) -> List[RoutingDecision]:
        return [self.route(message) for message in messages]

    def _apply_airport_context(
        self,
        message: AviationMessage,
        destinations: Set[str],
        reasons: List[str],
    ) -> None:
        for airport in {message.origin_airport, message.destination_airport}:
            if airport in HUB_AIRPORTS:
                destinations.add(f"hub_control_{airport.lower()}")
                reasons.append(f"hub_airport:{airport}")

    def _apply_operational_context(
        self,
        message: AviationMessage,
        destinations: Set[str],
        reasons: List[str],
    ) -> None:
        phase = str(message.context.get("flight_phase", "")).lower()
        if phase == "turnaround":
            destinations.update({"ground_handling", "turnaround_control"})
            reasons.append("phase:turnaround")
        elif phase == "in_flight":
            destinations.update({"flight_watch", "flight_dispatch"})
            reasons.append("phase:in_flight")

        event = str(message.payload.get("event", "")).lower()
        if event in SAFETY_EVENTS:
            destinations.update({"safety_control", "flight_dispatch", "emergency_response"})
            reasons.append(f"safety_event:{event}")
        if event in SECURITY_EVENTS or message.message_type.upper() == "SECURITY":
            destinations.update({"security_control", "airport_operations"})
            reasons.append(f"security_event:{event or message.message_type.lower()}")

    def _apply_weather_context(
        self,
        message: AviationMessage,
        destinations: Set[str],
        reasons: List[str],
    ) -> None:
        weather_level = int(message.context.get("weather_severity", 0) or 0)
        if message.message_type.upper() in {"METAR", "TAF", "SIGMET"} or weather_level:
            destinations.add("meteorology")
        if weather_level >= 3:
            destinations.update({"airport_operations", "flight_dispatch", "safety_control"})
            reasons.append(f"weather_severity:{weather_level}")

    def _apply_priority_context(
        self,
        message: AviationMessage,
        destinations: Set[str],
        reasons: List[str],
    ) -> None:
        if message.priority in {MessagePriority.URGENT.value, MessagePriority.CRITICAL.value}:
            destinations.update({"operations_supervisor", "priority_queue"})
            reasons.append(f"priority:{message.priority.lower()}")
        if message.priority == MessagePriority.DISTRESS.value:
            destinations.update(
                {
                    "emergency_response",
                    "operations_supervisor",
                    "safety_control",
                    "priority_queue",
                }
            )
            reasons.append("priority:distress")

    def _apply_regulatory_context(
        self,
        message: AviationMessage,
        destinations: Set[str],
        reasons: List[str],
    ) -> None:
        regulatory_zone = str(message.context.get("regulatory_zone", "")).upper()
        if regulatory_zone:
            destinations.add("compliance_monitoring")
            reasons.append(f"regulatory_zone:{regulatory_zone}")

    def _priority_channel(self, message: AviationMessage) -> str:
        if message.priority == MessagePriority.DISTRESS.value:
            return "distress"
        if message.priority == MessagePriority.CRITICAL.value:
            return "critical"
        if message.priority == MessagePriority.URGENT.value:
            return "urgent"
        if int(message.context.get("weather_severity", 0) or 0) >= 4:
            return "urgent"
        return "standard"

    def _route_key(self, message: AviationMessage, priority_channel: str) -> str:
        origin = message.origin_airport or "ZZZZ"
        destination = message.destination_airport or "ZZZZ"
        return ".".join(
            [
                "aviation",
                priority_channel,
                message.message_type.lower(),
                origin.lower(),
                destination.lower(),
            ]
        )

    def _ttl_seconds(self, priority_channel: str, message_type: str) -> int:
        if priority_channel == "distress":
            return 60
        if priority_channel in {"critical", "urgent"}:
            return 300
        if message_type in {"METAR", "TAF", "SIGMET", "NOTAM"}:
            return 1800
        return 3600
```

## Листинг 3. Генератор синтетического авиационного датасета

Файл: `app/aviation/generator.py`

Назначение: создание демонстрационного набора авиационных сообщений с воспроизводимым seed.

```python
from datetime import datetime, timedelta, timezone
import random
from typing import List, Optional
from uuid import uuid5, NAMESPACE_URL

from .models import AviationMessage, MessagePriority
from .real_data import RealAviationDataImporter


MESSAGE_TYPES = [
    "FPL", "DLA", "CNL", "CHG", "MVT", "LDM", "CPM", "NOTAM", "METAR",
    "TAF", "SIGMET", "SLOT", "PAXLST", "BAG", "MAINT", "TECHLOG",
    "SECURITY", "AFTN",
]
AIRPORTS = ["UUDD", "UUEE", "ULLI", "URSS", "UWGG", "USSS", "UTTT", "LEMD", "EDDF", "LTFM"]
OPERATORS = ["ESB Air", "NordLine", "Volga Wings", "SkyBridge", "AeroTransit"]
AIRCRAFT_TYPES = ["A320", "B738", "SU95", "B77F", "A321", "B763"]


class SyntheticAviationMessageGenerator:
    def __init__(self, seed: int = 42):
        self._random = random.Random(seed)

    def generate(
        self,
        count: int = 250,
        start_at: Optional[datetime] = None,
        include_real_data: bool = False,
    ) -> List[AviationMessage]:
        start = start_at or datetime(2026, 1, 1, tzinfo=timezone.utc)
        messages: List[AviationMessage] = []

        if include_real_data:
            messages.extend(RealAviationDataImporter().fetch())

        synthetic_count = max(count - len(messages), 0)
        for index in range(synthetic_count):
            message_type = MESSAGE_TYPES[index % len(MESSAGE_TYPES)]
            origin, destination = self._airport_pair()
            flight_number = self._flight_number()
            priority = self._priority(message_type, index)
            received_at = start + timedelta(minutes=index * self._random.randint(1, 7))
            payload = self._payload(message_type, priority)
            context = self._context(message_type, priority, payload)

            messages.append(
                AviationMessage(
                    message_id=str(uuid5(NAMESPACE_URL, f"esb-aviation-{index}-{flight_number}")),
                    message_type=message_type,
                    priority=priority,
                    origin_airport=origin,
                    destination_airport=destination,
                    flight_number=flight_number,
                    operator=self._random.choice(OPERATORS),
                    received_at=received_at,
                    payload=payload,
                    aircraft_registration=f"RA-{self._random.randint(10000, 99999)}",
                    context=context,
                )
            )

        return messages

    def _airport_pair(self) -> tuple[str, str]:
        origin = self._random.choice(AIRPORTS)
        destination = self._random.choice([airport for airport in AIRPORTS if airport != origin])
        return origin, destination

    def _flight_number(self) -> str:
        return f"ESB{self._random.randint(100, 9999)}"

    def _priority(self, message_type: str, index: int) -> str:
        if index % 53 == 0:
            return MessagePriority.DISTRESS.value
        if message_type in {"SIGMET", "SECURITY"} or index % 29 == 0:
            return MessagePriority.CRITICAL.value
        if message_type in {"DLA", "NOTAM", "MAINT"} or index % 11 == 0:
            return MessagePriority.URGENT.value
        return MessagePriority.NORMAL.value

    def _payload(self, message_type: str, priority: str) -> dict:
        if priority == MessagePriority.DISTRESS.value:
            return {"event": "emergency", "details": "PAN/MAYDAY operational escalation"}
        if message_type == "SECURITY":
            return {"event": "security_alert", "risk_score": self._random.randint(60, 95)}
        if message_type in {"METAR", "TAF", "SIGMET"}:
            return {
                "event": "weather_update",
                "wind_kt": self._random.randint(2, 45),
                "visibility_m": self._random.choice([400, 800, 1500, 3000, 10000]),
            }
        if message_type in {"LDM", "CPM"}:
            return {
                "event": "load_update",
                "cargo_kg": self._random.randint(500, 18000),
                "passengers": self._random.randint(20, 230),
            }
        if message_type in {"MAINT", "TECHLOG"}:
            return {
                "event": self._random.choice(["mel_item", "technical_delay", "service_release"]),
                "aircraft_type": self._random.choice(AIRCRAFT_TYPES),
            }
        if message_type in {"DLA", "CNL", "MVT"}:
            return {"event": self._random.choice(["delay", "off_block", "airborne", "arrival"])}
        return {"event": "operational_update"}

    def _context(self, message_type: str, priority: str, payload: dict) -> dict:
        weather_severity = 0
        if message_type == "SIGMET":
            weather_severity = self._random.randint(3, 5)
        elif message_type in {"METAR", "TAF"}:
            weather_severity = self._random.randint(0, 4)

        phase = self._random.choice(["preflight", "turnaround", "in_flight", "postflight"])
        if message_type in {"LDM", "CPM", "BAG"}:
            phase = "turnaround"
        if priority == MessagePriority.DISTRESS.value:
            phase = "in_flight"

        return {
            "flight_phase": phase,
            "weather_severity": weather_severity,
            "regulatory_zone": self._random.choice(["RF", "EU", "ICAO", ""]),
            "source_system": self._random.choice(["AODB", "DCS", "MRO", "AFTN", "MET"]),
            "schema_version": "1.0",
        }
```

## Листинг 4. Импорт публичных FAA/AWC данных и fallback snapshot

Файл: `app/aviation/real_data.py`

Назначение: импорт официальных FAA-примеров и погодных METAR/TAF данных NOAA Aviation Weather Center. При недоступности или частичном ответе live API используется локальный snapshot.

```python
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Iterable, List
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid5, NAMESPACE_URL

from .models import AviationMessage, MessagePriority


AWC_API_BASE = "https://aviationweather.gov/api/data"
DEFAULT_REAL_AIRPORTS = ["UUDD", "UUEE", "ULLI", "URSS", "EDDF", "LEMD"]
BUNDLED_AWC_SNAPSHOT = Path(__file__).resolve().parents[2] / "resources" / "awc_weather_snapshot_2026_04_26.json"


class RealAviationDataImporter:
    def __init__(self, airports: Iterable[str] = DEFAULT_REAL_AIRPORTS, timeout_seconds: int = 10):
        self.airports = [airport.upper() for airport in airports]
        self.timeout_seconds = timeout_seconds

    def fetch(self) -> List[AviationMessage]:
        messages = self.official_examples()
        live_weather = self._fetch_awc_product("metar") + self._fetch_awc_product("taf")
        snapshot_weather = self.bundled_awc_snapshot()
        expected_weather_count = len(self.airports) * 2
        weather_messages = live_weather

        if len(live_weather) < expected_weather_count:
            weather_messages = self._dedupe_messages([*live_weather, *snapshot_weather])

        messages.extend(weather_messages or snapshot_weather)
        return self._dedupe_messages(messages)

    def bundled_awc_snapshot(self) -> List[AviationMessage]:
        if not BUNDLED_AWC_SNAPSHOT.exists():
            return []

        try:
            data = json.loads(BUNDLED_AWC_SNAPSHOT.read_text(encoding="utf-8-sig"))
        except Exception:
            return []

        messages = [
            self._message_from_awc_row("metar", row)
            for row in data.get("metar", [])
            if isinstance(row, dict)
        ]
        messages.extend(
            self._message_from_awc_row("taf", row)
            for row in data.get("taf", [])
            if isinstance(row, dict)
        )
        return messages

    def _dedupe_messages(self, messages: Iterable[AviationMessage]) -> List[AviationMessage]:
        by_id = {}
        for message in messages:
            by_id[message.message_id] = message
        return list(by_id.values())

    def _fetch_awc_product(self, product: str) -> List[AviationMessage]:
        params = urlencode({"ids": ",".join(self.airports), "format": "json"})
        request = Request(
            f"{AWC_API_BASE}/{product}?{params}",
            headers={"User-Agent": "ESB-Aviation-Demo/1.0"},
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception:
            return []

        if isinstance(data, dict) and "value" in data:
            rows = data["value"]
        elif isinstance(data, list):
            rows = data
        else:
            rows = []

        return [self._message_from_awc_row(product, row) for row in rows]

    def _message_from_awc_row(self, product: str, row: dict) -> AviationMessage:
        icao_id = str(row.get("icaoId") or "ZZZZ").upper()
        raw_key = "rawTAF" if product == "taf" else "rawOb"
        raw_message = str(row.get(raw_key) or "")
        reported_at = row.get("reportTime") or row.get("issueTime") or row.get("receiptTime")
        received_at = self._parse_datetime(reported_at)
        flight_category = str(row.get("fltCat") or "")
        weather_severity = self._weather_severity(product, row, raw_message)

        return AviationMessage(
            message_id=str(uuid5(NAMESPACE_URL, f"awc-{product}-{icao_id}-{raw_message}")),
            message_type=product.upper(),
            priority=self._priority_from_weather(weather_severity, flight_category),
            origin_airport=icao_id,
            destination_airport=icao_id,
            flight_number=f"WX-{icao_id}",
            operator="NOAA Aviation Weather Center",
            received_at=received_at,
            payload={
                "event": "weather_update",
                "raw_message": raw_message,
                "flight_category": flight_category or None,
                "visibility": row.get("visib"),
                "wind_direction": row.get("wdir"),
                "wind_speed": row.get("wspd"),
                "source": "NOAA Aviation Weather Center Data API",
            },
            context={
                "source_system": "AWC",
                "data_kind": "live_weather",
                "weather_severity": weather_severity,
                "regulatory_zone": "ICAO",
                "schema_version": "1.0",
            },
        )
```

## Листинг 5. SQLite-хранилище авиационных сообщений

Файл: `app/aviation/repository.py`

Назначение: создание таблиц SQLite, сохранение сообщений, фильтрация, обновление и хранение решений маршрутизации.

```python
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
```

```python
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
```

## Листинг 6. REST API авиационного контура

Файл: `app/api/routes.py`

Назначение: endpoints для генерации датасета, импорта реальных данных, просмотра сообщений, создания/обновления сообщений и построения маршрутов.

```python
@router.post("/aviation/synthetic/generate", response_model=SyntheticDatasetResponse)
async def generate_synthetic_aviation_messages(
    count: int = Query(250, ge=1, le=10000),
    seed: int = Query(42, ge=0),
    include_real_data: bool = Query(False),
) -> SyntheticDatasetResponse:
    generator = SyntheticAviationMessageGenerator(seed=seed)
    inserted = aviation_repository.replace_messages(
        generator.generate(count=count, include_real_data=include_real_data)
    )
    return SyntheticDatasetResponse(db_path=str(aviation_repository.db_path), inserted=inserted)


@router.post("/aviation/real/import", response_model=SyntheticDatasetResponse)
async def import_real_aviation_messages() -> SyntheticDatasetResponse:
    messages = RealAviationDataImporter().fetch()
    current_messages = aviation_repository.list_messages(limit=10000)
    by_id = {message.message_id: message for message in current_messages}
    for message in messages:
        by_id[message.message_id] = message

    inserted = aviation_repository.replace_messages(by_id.values())
    return SyntheticDatasetResponse(db_path=str(aviation_repository.db_path), inserted=inserted)


@router.get("/aviation/overview", response_model=AviationOverviewSchema)
async def get_aviation_overview() -> AviationOverviewSchema:
    return AviationOverviewSchema(**aviation_repository.overview())


@router.get("/aviation/messages", response_model=List[AviationMessageSchema])
async def list_aviation_messages(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    message_type: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    airport: Optional[str] = Query(None),
) -> List[AviationMessageSchema]:
    messages = aviation_repository.list_messages(
        limit=limit,
        offset=offset,
        message_type=message_type,
        priority=priority,
        airport=airport,
    )
    return [AviationMessageSchema(**message.to_dict()) for message in messages]


@router.post("/aviation/messages", response_model=AviationMessageSchema, status_code=201)
async def create_aviation_message(message: AviationMessageSchema) -> AviationMessageSchema:
    try:
        created = aviation_repository.add_message(AviationMessage.from_dict(message.model_dump()))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to create aviation message: {exc}")
    return AviationMessageSchema(**created.to_dict())


@router.put("/aviation/messages/{message_id}", response_model=AviationMessageSchema)
async def update_aviation_message(
    message_id: str,
    message: AviationMessageSchema,
) -> AviationMessageSchema:
    updated = aviation_repository.update_message(
        message_id,
        AviationMessage.from_dict(message.model_dump()),
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Aviation message not found")
    return AviationMessageSchema(**updated.to_dict())


@router.post("/aviation/messages/{message_id}/route", response_model=RoutingDecisionSchema)
async def route_stored_aviation_message(message_id: str) -> RoutingDecisionSchema:
    message = aviation_repository.get_message(message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="Aviation message not found")
    decision = aviation_router.route(message)
    aviation_repository.save_routing_decision(decision)
    return RoutingDecisionSchema(**decision.to_dict())


@router.get("/aviation/routes")
async def list_aviation_routes(limit: int = Query(50, ge=1, le=500)) -> List[dict]:
    return aviation_repository.list_routing_decisions(limit=limit)
```

## Листинг 7. Настройка пути к датасету

Файл: `app/core/config.py`

Назначение: хранение пути к SQLite-датасету и директории логов.

```python
class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://esb_admin:25565@localhost:5432/esb_db"
    ).strip()

    LOG_DIR: str = os.getenv("LOG_DIR", os.getenv("app/logs", "app/logs")).strip()

    AVIATION_DB_PATH: str = os.getenv(
        "AVIATION_DB_PATH",
        "resources/synthetic_aviation_messages.db",
    ).strip()
```

## Листинг 8. Основная структура HTML-интерфейса

Файл: `app/templates/index.html`

Назначение: статическая single-page консоль для демонстрации авиационного ESB.

```html
<body>
    <div class="app-shell">
        <header class="topbar">
            <div class="brand">
                <div class="brand-mark" aria-hidden="true">ESB</div>
                <div>
                    <h1>ESB Aviation</h1>
                    <p>Контекстная маршрутизация авиаоперационных сообщений</p>
                </div>
            </div>
        </header>

        <main class="workspace">
            <aside class="panel left-rail" aria-label="Фильтры и действия">
                <section class="rail-section">
                    <h2 class="rail-title">Данные</h2>
                    <div class="actions-grid">
                        <button id="refreshButton" type="button">Обновить</button>
                        <button id="generateButton" class="warning" type="button">Синтетика + real</button>
                        <button id="importButton" class="secondary" type="button">Импорт FAA/AWC</button>
                    </div>
                </section>

                <section class="rail-section">
                    <h2 class="rail-title">Фильтры</h2>
                    <div class="stack">
                        <label for="searchFilter">Поиск
                            <input id="searchFilter" autocomplete="off" placeholder="ESB900, UUDD, operator">
                        </label>
                        <label for="typeFilter">Тип сообщения
                            <select id="typeFilter"></select>
                        </label>
                        <label for="priorityFilter">Приоритет
                            <select id="priorityFilter"></select>
                        </label>
                        <label for="airportFilter">Аэропорт
                            <input id="airportFilter" autocomplete="off" maxlength="4" placeholder="UUDD">
                        </label>
                    </div>
                </section>
            </aside>

            <section class="panel" aria-label="Рабочая очередь сообщений">
                <div class="stat-grid" id="statGrid"></div>
                <div class="panel-header">
                    <div>
                        <h2>Очередь сообщений</h2>
                        <div id="queueMeta" class="muted small">0 записей</div>
                    </div>
                    <span id="selectedBadge" class="badge unrouted">Нет выбора</span>
                </div>
                <div class="panel-body table-shell">
                    <table class="message-table">
                        <thead>
                            <tr>
                                <th>Priority</th>
                                <th>Type</th>
                                <th>Flight</th>
                                <th>Route</th>
                                <th>Operator / Source</th>
                                <th>Event</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody id="messageRows"></tbody>
                    </table>
                </div>
            </section>

            <aside class="panel side-panel" aria-label="Детали и маршрутизация">
                <!-- Форма сообщения, блок маршрутизации и последние решения -->
            </aside>
        </main>
    </div>
</body>
```

## Листинг 9. Состояние frontend-приложения и API wrapper

Файл: `app/templates/index.html`

Назначение: хранение состояния UI и безопасная работа с REST API.

```javascript
const API_BASE = "/api/v1";
const MESSAGE_TYPES = ["FPL", "DLA", "CNL", "CHG", "MVT", "LDM", "CPM", "NOTAM", "METAR", "TAF", "SIGMET", "SLOT", "PAXLST", "BAG", "MAINT", "TECHLOG", "SECURITY", "AFTN"];
const PRIORITIES = ["NORMAL", "URGENT", "CRITICAL", "DISTRESS"];
const PHASES = ["preflight", "turnaround", "in_flight", "postflight"];

const state = {
    overview: null,
    messages: [],
    filteredMessages: [],
    routes: [],
    selectedMessage: null,
    decision: null,
    busy: false
};

async function apiRequest(path, options = {}) {
    const response = await fetch(`${API_BASE}${path}`, {
        headers: {"Content-Type": "application/json"},
        ...options
    });
    if (!response.ok) {
        let detail = await response.text();
        try {
            const parsed = JSON.parse(detail);
            detail = parsed.detail || detail;
        } catch (error) {
            // Keep original response text.
        }
        throw new Error(`${response.status}: ${detail}`);
    }
    return response.json();
}
```

## Листинг 10. Загрузка данных и клиентская фильтрация

Файл: `app/templates/index.html`

Назначение: получение overview, сообщений и решений маршрутизации; фильтрация по поиску, источнику и фазе рейса.

```javascript
async function loadAll() {
    setBusy(true);
    setStatus("Загрузка данных", "loading");
    try {
        const params = new URLSearchParams({
            limit: "300",
            message_type: dom.typeFilter.value,
            priority: dom.priorityFilter.value,
            airport: dom.airportFilter.value.trim().toUpperCase()
        });
        const [overview, messages, routes] = await Promise.all([
            apiRequest("/aviation/overview"),
            apiRequest(`/aviation/messages?${params.toString()}`),
            apiRequest("/aviation/routes?limit=80")
        ]);
        state.overview = overview;
        state.messages = messages;
        state.routes = routes;
        syncDynamicFilters();
        applyClientFilters();
        renderOverview();
        renderRoutes();
        setStatus("Готово", "success");
    } catch (error) {
        setStatus(readableError(error), "error");
    } finally {
        setBusy(false);
    }
}

function applyClientFilters() {
    const search = dom.searchFilter.value.trim().toLowerCase();
    const source = dom.sourceFilter.value;
    const phase = dom.phaseFilter.value;

    state.filteredMessages = state.messages.filter((message) => {
        const text = [
            message.message_id,
            message.message_type,
            message.flight_number,
            message.operator,
            message.origin_airport,
            message.destination_airport,
            message.payload?.event,
            message.context?.source_system
        ].filter(Boolean).join(" ").toLowerCase();

        if (search && !text.includes(search)) {
            return false;
        }
        if (source && (message.context?.source_system || "unknown") !== source) {
            return false;
        }
        if (phase && message.context?.flight_phase !== phase) {
            return false;
        }
        return true;
    });

    renderMessages();
}
```

## Листинг 11. Безопасная отрисовка таблицы сообщений

Файл: `app/templates/index.html`

Назначение: вывод очереди сообщений без небезопасного `innerHTML`, через создание DOM-элементов.

```javascript
function renderMessages() {
    const routeIds = new Set(state.routes.map((route) => route.message_id));
    dom.messageRows.replaceChildren();
    dom.emptyMessages.hidden = state.filteredMessages.length > 0;
    dom.queueMeta.textContent = `${state.filteredMessages.length} из ${state.messages.length} загруженных`;

    state.filteredMessages.forEach((message) => {
        const tr = document.createElement("tr");
        if (state.selectedMessage?.message_id === message.message_id) {
            tr.className = "active";
        }
        tr.tabIndex = 0;
        tr.setAttribute("role", "button");
        tr.setAttribute("aria-label", `Выбрать сообщение ${message.message_type} ${message.flight_number}`);
        tr.addEventListener("click", () => selectMessage(message));
        tr.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                selectMessage(message);
            }
        });

        tr.appendChild(cell(badge(message.priority, message.priority.toLowerCase())));
        tr.appendChild(cell(node("span", "strong", message.message_type)));
        tr.appendChild(cell(node("span", null, message.flight_number || "-")));
        tr.appendChild(cell(node("span", "mono", `${message.origin_airport || "ZZZZ"} > ${message.destination_airport || "ZZZZ"}`)));
        tr.appendChild(cell(operatorBlock(message)));
        tr.appendChild(cell(node("span", null, message.payload?.event || "-")));
        tr.appendChild(cell(badge(routeIds.has(message.message_id) ? "routed" : "unrouted", routeIds.has(message.message_id) ? "routed" : "unrouted")));
        dom.messageRows.appendChild(tr);
    });

    updateSelectedBadge();
}
```

## Листинг 12. Создание, обновление и маршрутизация сообщения из UI

Файл: `app/templates/index.html`

Назначение: выполнение основных пользовательских сценариев без Swagger.

```javascript
function formMessage() {
    const payload = readJsonField(dom.payload, "Payload");
    const context = readJsonField(dom.context, "Context");
    return {
        message_id: dom.messageId.value.trim() || `demo-${Date.now()}`,
        message_type: dom.messageType.value.toUpperCase(),
        priority: dom.priority.value.toUpperCase(),
        origin_airport: dom.origin.value.trim().toUpperCase(),
        destination_airport: dom.destination.value.trim().toUpperCase(),
        flight_number: dom.flightNumber.value.trim(),
        operator: dom.operator.value.trim(),
        received_at: state.selectedMessage?.received_at || new Date().toISOString(),
        payload,
        aircraft_registration: dom.registration.value.trim() || null,
        context
    };
}

async function createMessage() {
    try {
        setBusy(true);
        setStatus("Создание сообщения", "loading");
        const message = formMessage();
        const created = await apiRequest("/aviation/messages", {
            method: "POST",
            body: JSON.stringify(message)
        });
        state.selectedMessage = created;
        await loadAll();
        selectMessage(created);
        setStatus("Сообщение создано", "success");
    } catch (error) {
        setStatus(readableError(error), "error");
    } finally {
        setBusy(false);
    }
}

async function updateMessage() {
    try {
        setBusy(true);
        setStatus("Сохранение сообщения", "loading");
        const message = formMessage();
        const updated = await apiRequest(`/aviation/messages/${encodeURIComponent(message.message_id)}`, {
            method: "PUT",
            body: JSON.stringify(message)
        });
        state.selectedMessage = updated;
        await loadAll();
        selectMessage(updated);
        setStatus("Сообщение обновлено", "success");
    } catch (error) {
        setStatus(readableError(error), "error");
    } finally {
        setBusy(false);
    }
}

async function routeSelected() {
    try {
        setBusy(true);
        setStatus("Построение маршрута", "loading");
        const messageId = dom.messageId.value.trim();
        if (!messageId) {
            throw new Error("Укажите ID сообщения для маршрутизации");
        }
        const decision = await apiRequest(
            `/aviation/messages/${encodeURIComponent(messageId)}/route`,
            {method: "POST"}
        );
        state.decision = decision;
        await loadAll();
        renderDecision();
        renderMessages();
        setStatus("Маршрут построен и сохранен", "success");
    } catch (error) {
        setStatus(readableError(error), "error");
    } finally {
        setBusy(false);
    }
}
```

## Листинг 13. Объяснимая визуализация маршрута

Файл: `app/templates/index.html`

Назначение: отображение канала, route key, TTL, получателей и человекочитаемых причин маршрутизации.

```javascript
function renderDecision() {
    const decision = state.decision;
    dom.decisionPanel.replaceChildren();
    if (!decision) {
        dom.decisionBadge.className = "badge standard";
        dom.decisionBadge.textContent = state.selectedMessage ? "Готово к расчету" : "Ожидает";
        dom.decisionPanel.appendChild(buildPendingDecision());
        return;
    }

    dom.decisionBadge.className = `badge ${decision.priority_channel}`;
    dom.decisionBadge.textContent = decision.priority_channel;

    const card = node("article", "decision-card");
    const header = node("div", "decision-header");
    header.appendChild(badge(decision.priority_channel, decision.priority_channel));
    header.appendChild(node("span", "muted small", ttlLabel(decision.ttl_seconds)));
    card.appendChild(header);
    card.appendChild(keyValue("Route key", decision.route_key));
    card.appendChild(keyValue("Message ID", decision.message_id));
    card.appendChild(keyValue("TTL", ttlLabel(decision.ttl_seconds)));
    card.appendChild(sectionList("Получатели", decision.destinations, "chip destination"));
    card.appendChild(sectionList("Почему такой маршрут", decision.reasons.map(explainReason), "chip reason"));
    dom.decisionPanel.appendChild(card);
}

function explainReason(reason) {
    const text = String(reason || "");
    if (text.startsWith("type:")) return `Тип сообщения ${text.slice(5)} определил базовый маршрут`;
    if (text.startsWith("hub_airport:")) return `Аэропорт-хаб ${text.slice(12)} добавил hub control`;
    if (text === "phase:turnaround") return "Фаза turnaround добавила ground handling и turnaround control";
    if (text === "phase:in_flight") return "Фаза in_flight добавила flight watch и dispatch";
    if (text.startsWith("weather_severity:")) return `Погодная опасность ${text.slice(17)} включила safety/operations escalation`;
    if (text.startsWith("priority:distress")) return "Приоритет DISTRESS включил аварийный канал и TTL 60 секунд";
    if (text.startsWith("priority:")) return `Приоритет ${text.slice(9).toUpperCase()} добавил supervisor и priority queue`;
    if (text.startsWith("security_event:")) return `Security event ${text.slice(15)} добавил security routing`;
    if (text.startsWith("safety_event:")) return `Safety event ${text.slice(13)} добавил emergency response`;
    if (text.startsWith("regulatory_zone:")) return `Regulatory zone ${text.slice(16)} добавила compliance monitoring`;
    return text;
}
```
