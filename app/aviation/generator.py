from datetime import datetime, timedelta, timezone
import random
from typing import List, Optional
from uuid import uuid5, NAMESPACE_URL

from .models import AviationMessage, MessagePriority
from .real_data import RealAviationDataImporter


MESSAGE_TYPES = [
    "FPL",
    "DLA",
    "CNL",
    "CHG",
    "MVT",
    "LDM",
    "CPM",
    "NOTAM",
    "METAR",
    "TAF",
    "SIGMET",
    "SLOT",
    "PAXLST",
    "BAG",
    "MAINT",
    "TECHLOG",
    "SECURITY",
    "AFTN",
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
