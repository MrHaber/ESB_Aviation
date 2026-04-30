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
