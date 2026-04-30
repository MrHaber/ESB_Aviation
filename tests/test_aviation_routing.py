import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from app.aviation.generator import SyntheticAviationMessageGenerator
from app.aviation.models import AviationMessage
from app.aviation.real_data import RealAviationDataImporter
from app.aviation.repository import AviationMessageRepository
from app.aviation.routing import ContextAwareAviationRouter


def make_message(**overrides) -> AviationMessage:
    data = {
        "message_id": "msg-001",
        "message_type": "FPL",
        "priority": "NORMAL",
        "origin_airport": "UUDD",
        "destination_airport": "ULLI",
        "flight_number": "ESB123",
        "operator": "ESB Air",
        "received_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "aircraft_registration": "RA-12345",
        "payload": {"event": "operational_update"},
        "context": {"flight_phase": "preflight", "weather_severity": 0},
    }
    data.update(overrides)
    return AviationMessage.from_dict(data)


class ContextAwareAviationRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.router = ContextAwareAviationRouter()

    def test_routes_turnaround_load_message_to_ground_and_load_control(self) -> None:
        message = make_message(
            message_type="LDM",
            origin_airport="UUDD",
            destination_airport="EDDF",
            payload={"event": "load_update", "passengers": 168},
            context={"flight_phase": "turnaround", "weather_severity": 0},
        )

        decision = self.router.route(message)

        self.assertIn("load_control", decision.destinations)
        self.assertIn("ground_handling", decision.destinations)
        self.assertIn("turnaround_control", decision.destinations)
        self.assertIn("hub_control_uudd", decision.destinations)
        self.assertEqual("standard", decision.priority_channel)
        self.assertTrue(decision.route_key.startswith("aviation.standard.ldm"))

    def test_escalates_distress_emergency_message(self) -> None:
        message = make_message(
            message_id="msg-distress",
            message_type="MVT",
            priority="DISTRESS",
            payload={"event": "emergency"},
            context={"flight_phase": "in_flight", "weather_severity": 0},
        )

        decision = self.router.route(message)

        self.assertEqual("distress", decision.priority_channel)
        self.assertEqual(60, decision.ttl_seconds)
        self.assertIn("emergency_response", decision.destinations)
        self.assertIn("operations_supervisor", decision.destinations)
        self.assertIn("safety_control", decision.destinations)
        self.assertIn("priority:distress", decision.reasons)

    def test_escalates_severe_weather_even_without_urgent_priority(self) -> None:
        message = make_message(
            message_id="msg-weather",
            message_type="METAR",
            priority="NORMAL",
            payload={"event": "weather_update", "visibility_m": 400},
            context={"flight_phase": "preflight", "weather_severity": 4},
        )

        decision = self.router.route(message)

        self.assertEqual("urgent", decision.priority_channel)
        self.assertEqual(300, decision.ttl_seconds)
        self.assertIn("meteorology", decision.destinations)
        self.assertIn("flight_dispatch", decision.destinations)
        self.assertIn("safety_control", decision.destinations)
        self.assertIn("weather_severity:4", decision.reasons)

    def test_unknown_message_type_is_routed_to_triage(self) -> None:
        message = make_message(message_type="CUSTOM", origin_airport="", destination_airport="")

        decision = self.router.route(message)

        self.assertIn("message_triage", decision.destinations)
        self.assertEqual("aviation.standard.custom.zzzz.zzzz", decision.route_key)


class SyntheticAviationGeneratorTests(unittest.TestCase):
    def test_generator_creates_deterministic_operational_dataset(self) -> None:
        first = SyntheticAviationMessageGenerator(seed=7).generate(count=36)
        second = SyntheticAviationMessageGenerator(seed=7).generate(count=36)

        self.assertEqual(36, len(first))
        self.assertEqual([m.to_dict() for m in first], [m.to_dict() for m in second])
        self.assertGreaterEqual(len({message.message_type for message in first}), 18)
        self.assertTrue(any(message.priority == "DISTRESS" for message in first))

    def test_generator_can_include_real_public_messages(self) -> None:
        messages = SyntheticAviationMessageGenerator(seed=7).generate(count=40, include_real_data=True)

        source_systems = {message.context.get("source_system") for message in messages}
        self.assertEqual(40, len(messages))
        self.assertIn("FAA", source_systems)
        self.assertIn("AWC", source_systems)


class RealAviationDataImporterTests(unittest.TestCase):
    def test_importer_loads_official_examples_and_bundled_awc_snapshot(self) -> None:
        messages = RealAviationDataImporter(timeout_seconds=1).fetch()
        source_systems = {message.context.get("source_system") for message in messages}

        self.assertGreaterEqual(len(messages), 15)
        self.assertIn("FAA", source_systems)
        self.assertIn("AWC", source_systems)
        self.assertTrue(any(message.message_type == "METAR" for message in messages))
        self.assertTrue(any(message.message_type == "TAF" for message in messages))


class AviationMessageRepositoryTests(unittest.TestCase):
    def test_repository_persists_filters_and_routes_messages(self) -> None:
        messages = [
            make_message(message_id="repo-1", message_type="LDM", priority="NORMAL"),
            make_message(message_id="repo-2", message_type="SIGMET", priority="CRITICAL"),
            make_message(
                message_id="repo-3",
                message_type="SECURITY",
                priority="CRITICAL",
                origin_airport="LEMD",
                destination_airport="EDDF",
            ),
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            repository = AviationMessageRepository(Path(tmp_dir) / "aviation.db")
            inserted = repository.replace_messages(messages)

            self.assertEqual(3, inserted)
            self.assertEqual(3, repository.count_messages())
            self.assertEqual(["repo-2"], [m.message_id for m in repository.list_messages(message_type="SIGMET")])
            self.assertEqual(2, len(repository.list_messages(airport="UUDD")))

            decision = ContextAwareAviationRouter().route(repository.get_message("repo-2"))
            repository.save_routing_decision(decision)

            stored = repository.get_message("repo-2")
            self.assertIsNotNone(stored)
            self.assertEqual("SIGMET", stored.message_type)
            self.assertEqual(1, len(repository.list_routing_decisions()))

    def test_repository_updates_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repository = AviationMessageRepository(Path(tmp_dir) / "aviation.db")
            repository.replace_messages([make_message(message_id="update-1", priority="NORMAL")])

            updated = repository.update_message(
                "update-1",
                make_message(message_id="ignored", priority="URGENT", payload={"event": "delay"}),
            )

            self.assertIsNotNone(updated)
            self.assertEqual("update-1", updated.message_id)
            self.assertEqual("URGENT", repository.get_message("update-1").priority)
            self.assertIsNone(repository.update_message("missing", make_message()))


if __name__ == "__main__":
    unittest.main()
