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

OFFICIAL_ICAO_EXAMPLES = [
    {
        "message_type": "FPL",
        "raw": "(FPLAWE/KZDC004-AWE603-IS-A319/M-SDIW/C-KBWI1230-N0291F090 SWANN3 SWANN V214 DQO DCT-KPHL0017-RMK/DVRSN)",
        "source": "FAA ICAO message examples",
        "origin_airport": "KBWI",
        "destination_airport": "KPHL",
        "flight_number": "AWE603",
    },
    {
        "message_type": "CNL",
        "raw": "(CNLPOP/KZDC015POP/KZDC008-FRTTN23-KPOB)",
        "source": "FAA ICAO message examples",
        "origin_airport": "KPOB",
        "destination_airport": "KPOB",
        "flight_number": "FRTTN23",
    },
    {
        "message_type": "CHG",
        "raw": "(CHG-N96747-KFDK-KDAN-15/N0110F080 DCT JYO DCT CSN DCT)",
        "source": "FAA ICAO message examples",
        "origin_airport": "KFDK",
        "destination_airport": "KDAN",
        "flight_number": "N96747",
    },
]


class RealAviationDataImporter:
    def __init__(self, airports: Iterable[str] = DEFAULT_REAL_AIRPORTS, timeout_seconds: int = 10):
        self.airports = [airport.upper() for airport in airports]
        self.timeout_seconds = timeout_seconds

    def fetch(self) -> List[AviationMessage]:
        messages = self.official_examples()
        live_weather = self._fetch_awc_product("metar") + self._fetch_awc_product("taf")
        messages.extend(live_weather or self.bundled_awc_snapshot())
        return messages

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

    def official_examples(self) -> List[AviationMessage]:
        received_at = datetime.now(timezone.utc)
        messages: List[AviationMessage] = []

        for index, example in enumerate(OFFICIAL_ICAO_EXAMPLES, start=1):
            raw = example["raw"]
            messages.append(
                AviationMessage(
                    message_id=str(uuid5(NAMESPACE_URL, f"faa-icao-example-{index}-{raw}")),
                    message_type=example["message_type"],
                    priority=MessagePriority.NORMAL.value,
                    origin_airport=example["origin_airport"],
                    destination_airport=example["destination_airport"],
                    flight_number=example["flight_number"],
                    operator="Public FAA example",
                    received_at=received_at,
                    payload={
                        "event": "official_icao_example",
                        "raw_message": raw,
                        "source": example["source"],
                    },
                    context={
                        "source_system": "FAA",
                        "data_kind": "official_example",
                        "schema_version": "1.0",
                    },
                )
            )

        return messages

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
                "station_name": row.get("name"),
                "flight_category": flight_category or None,
                "temperature_c": row.get("temp"),
                "visibility": row.get("visib"),
                "wind_direction": row.get("wdir"),
                "wind_speed": row.get("wspd"),
                "clouds": row.get("clouds") or [],
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

    def _parse_datetime(self, value: object) -> datetime:
        if isinstance(value, str) and value:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return datetime.now(timezone.utc)

    def _priority_from_weather(self, weather_severity: int, flight_category: str) -> str:
        if weather_severity >= 4 or flight_category in {"LIFR", "IFR"}:
            return MessagePriority.URGENT.value
        if weather_severity >= 3:
            return MessagePriority.CRITICAL.value
        return MessagePriority.NORMAL.value

    def _weather_severity(self, product: str, row: dict, raw_message: str) -> int:
        text = raw_message.upper()
        if "+TS" in text or "+SH" in text or "FZRA" in text or row.get("fltCat") == "LIFR":
            return 4
        if "CB" in text or "SIGMET" in text or row.get("fltCat") == "IFR":
            return 3
        if product == "taf" and ("TEMPO" in text or "PROB" in text):
            return 2
        return 1
