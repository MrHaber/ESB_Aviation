import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import routes
from app.aviation.repository import AviationMessageRepository


class AviationApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.repository = AviationMessageRepository(Path(self.tmp_dir.name) / "api.db")
        routes.aviation_repository = self.repository
        app = FastAPI()
        app.include_router(routes.router)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def message_payload(self, message_id: str = "api-001") -> dict:
        return {
            "message_id": message_id,
            "message_type": "MVT",
            "priority": "NORMAL",
            "origin_airport": "UUDD",
            "destination_airport": "ULLI",
            "flight_number": "ESB901",
            "operator": "ESB Air",
            "received_at": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
            "payload": {"event": "operational_update"},
            "aircraft_registration": "RA-90100",
            "context": {"flight_phase": "turnaround", "weather_severity": 0},
        }

    def test_backend_get_post_update_and_route_handlers(self) -> None:
        create_response = self.client.post("/api/v1/aviation/messages", json=self.message_payload())
        self.assertEqual(201, create_response.status_code)
        self.assertEqual("api-001", create_response.json()["message_id"])

        list_response = self.client.get("/api/v1/aviation/messages")
        self.assertEqual(200, list_response.status_code)
        self.assertEqual(1, len(list_response.json()))

        get_response = self.client.get("/api/v1/aviation/messages/api-001")
        self.assertEqual(200, get_response.status_code)
        self.assertEqual("MVT", get_response.json()["message_type"])

        updated_payload = self.message_payload()
        updated_payload["priority"] = "URGENT"
        updated_payload["payload"] = {"event": "delay"}
        update_response = self.client.put("/api/v1/aviation/messages/api-001", json=updated_payload)
        self.assertEqual(200, update_response.status_code)
        self.assertEqual("URGENT", update_response.json()["priority"])

        route_response = self.client.post("/api/v1/aviation/messages/api-001/route")
        self.assertEqual(200, route_response.status_code)
        self.assertIn("priority_queue", route_response.json()["destinations"])

        routes_response = self.client.get("/api/v1/aviation/routes")
        self.assertEqual(200, routes_response.status_code)
        self.assertEqual(1, len(routes_response.json()))

        overview_response = self.client.get("/api/v1/aviation/overview")
        self.assertEqual(200, overview_response.status_code)
        self.assertEqual(1, overview_response.json()["total_messages"])

    def test_backend_returns_not_found_for_missing_message_and_route(self) -> None:
        get_response = self.client.get("/api/v1/aviation/messages/missing")
        route_response = self.client.post("/api/v1/aviation/messages/missing/route")

        self.assertEqual(404, get_response.status_code)
        self.assertEqual("Aviation message not found", get_response.json()["detail"])
        self.assertEqual(404, route_response.status_code)
        self.assertEqual("Aviation message not found", route_response.json()["detail"])

    def test_backend_routes_inline_message_without_persisting_decision(self) -> None:
        route_response = self.client.post("/api/v1/aviation/route", json=self.message_payload("inline-001"))
        routes_response = self.client.get("/api/v1/aviation/routes")

        self.assertEqual(200, route_response.status_code)
        self.assertEqual("inline-001", route_response.json()["message_id"])
        self.assertIn("flight_dispatch", route_response.json()["destinations"])
        self.assertEqual([], routes_response.json())

    def test_backend_filters_messages_by_priority_and_airport(self) -> None:
        urgent_payload = self.message_payload("urgent-001")
        urgent_payload["priority"] = "URGENT"
        urgent_payload["destination_airport"] = "EDDF"
        normal_payload = self.message_payload("normal-001")
        normal_payload["origin_airport"] = "ULLI"
        normal_payload["destination_airport"] = "UUEE"

        self.client.post("/api/v1/aviation/messages", json=urgent_payload)
        self.client.post("/api/v1/aviation/messages", json=normal_payload)

        urgent_response = self.client.get("/api/v1/aviation/messages?priority=urgent")
        airport_response = self.client.get("/api/v1/aviation/messages?airport=UUEE")

        self.assertEqual(["urgent-001"], [item["message_id"] for item in urgent_response.json()])
        self.assertEqual(["normal-001"], [item["message_id"] for item in airport_response.json()])

    def test_backend_generates_and_imports_public_real_messages(self) -> None:
        generate_response = self.client.post(
            "/api/v1/aviation/synthetic/generate?count=30&seed=3&include_real_data=true"
        )
        self.assertEqual(200, generate_response.status_code)
        self.assertEqual(30, generate_response.json()["inserted"])

        real_messages = self.client.get("/api/v1/aviation/messages?message_type=METAR")
        self.assertEqual(200, real_messages.status_code)
        self.assertGreaterEqual(len(real_messages.json()), 1)

        import_response = self.client.post("/api/v1/aviation/real/import")
        self.assertEqual(200, import_response.status_code)
        self.assertGreaterEqual(import_response.json()["inserted"], 15)


if __name__ == "__main__":
    unittest.main()
