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
