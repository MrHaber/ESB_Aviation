import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import requests
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.transformers.binary_to_json import binary_to_json
from app.transformers.csv_to_json import csv_to_json
from app.transformers.odata_to_json import odata_to_json
from app.transformers.xml_to_json import xml_to_json
from app.utils.helpers import create_trigger, generate_request_id, get_current_timestamp


class TransformerTests(unittest.TestCase):
    def test_csv_xml_and_binary_transformers_return_json_compatible_data(self) -> None:
        csv_result = csv_to_json("flight,status\nESB101,ON_TIME\nESB102,DELAYED\n")
        xml_result = xml_to_json("<flight><number>ESB101</number><status>ON_TIME</status></flight>")
        binary_result = binary_to_json(b"\x00\x01ABC")

        self.assertEqual(
            [
                {"flight": "ESB101", "status": "ON_TIME"},
                {"flight": "ESB102", "status": "DELAYED"},
            ],
            csv_result,
        )
        self.assertEqual("ESB101", xml_result["flight"]["number"])
        self.assertEqual({"data": [0, 1, 65, 66, 67]}, binary_result)

    @patch("app.transformers.odata_to_json.requests.get")
    def test_odata_transformer_requests_json_format(self, mock_get: Mock) -> None:
        response = Mock()
        response.json.return_value = {"value": [{"id": 1, "status": "ok"}]}
        response.raise_for_status.return_value = None
        mock_get.return_value = response

        result = odata_to_json("https://example.test/odata/Flights", params={"$top": 1})

        self.assertEqual({"value": [{"id": 1, "status": "ok"}]}, result)
        mock_get.assert_called_once_with(
            "https://example.test/odata/Flights",
            params={"$top": 1, "$format": "json"},
        )

    @patch("app.transformers.odata_to_json.requests.get")
    def test_odata_transformer_returns_none_on_request_failure(self, mock_get: Mock) -> None:
        mock_get.side_effect = requests.exceptions.RequestException("network is unavailable")

        self.assertIsNone(odata_to_json("https://example.test/odata/Flights"))


class HelperTests(unittest.TestCase):
    def test_generate_request_id_is_uuid_like_and_unique(self) -> None:
        first = generate_request_id()
        second = generate_request_id()

        self.assertNotEqual(first, second)
        self.assertEqual(36, len(first))
        self.assertEqual("-", first[8])

    def test_current_timestamp_is_utc_naive_datetime_for_database_logs(self) -> None:
        timestamp = get_current_timestamp()

        self.assertIsInstance(timestamp, datetime)
        self.assertIsNone(timestamp.tzinfo)

    def test_create_trigger_builds_interval_and_future_date_triggers(self) -> None:
        interval_trigger = create_trigger({"interval": "5 minutes"})
        date_trigger = create_trigger({"run_at": "2099-01-01T12:00:00Z"})

        self.assertIsInstance(interval_trigger, IntervalTrigger)
        self.assertIsInstance(date_trigger, DateTrigger)

    def test_create_trigger_rejects_invalid_or_past_schedules(self) -> None:
        self.assertIsNone(create_trigger({"interval": "soon"}))
        self.assertIsNone(create_trigger({"run_at": "bad-date"}))
        self.assertIsNone(create_trigger({"run_at": "2000-01-01T00:00:00Z"}))
        self.assertIsNone(create_trigger({}))

    def test_moscow_time_run_at_is_converted_to_utc(self) -> None:
        trigger = create_trigger({"run_at": "2099-01-01T12:00:00"}, moscow_time=True)

        self.assertIsInstance(trigger, DateTrigger)
        self.assertEqual(
            datetime(2099, 1, 1, 9, 0, tzinfo=timezone.utc),
            trigger.run_date,
        )


if __name__ == "__main__":
    unittest.main()
