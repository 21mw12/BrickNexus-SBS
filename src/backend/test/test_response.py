import json
import unittest
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from app.common.Response import Response


class ResponseTests(unittest.TestCase):
    def test_success_serializes_json_compatible_values(self):
        response = Response.success(
            {
                "created_at": datetime(
                    2026, 8, 4, 12, 30, 45, tzinfo=timezone.utc
                ),
                "day": date(2026, 8, 4),
                "amount": Decimal("12.50"),
                "asset_id": UUID("d779c00f-c4ca-4977-a6f7-b04737cf2298"),
            }
        )

        payload = json.loads(response.body)

        self.assertEqual(payload["data"]["created_at"], "2026-08-04T12:30:45Z")
        self.assertEqual(payload["data"]["day"], "2026-08-04")
        self.assertEqual(payload["data"]["amount"], "12.50")
        self.assertEqual(
            payload["data"]["asset_id"],
            "d779c00f-c4ca-4977-a6f7-b04737cf2298",
        )


if __name__ == "__main__":
    unittest.main()
