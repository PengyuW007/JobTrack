import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from visualization.Workbench import milliseconds_until_next_midnight


class WorkbenchScheduleTests(unittest.TestCase):
    def test_next_midnight_uses_toronto_time(self):
        now = datetime(2026, 9, 10, 23, 30, tzinfo=ZoneInfo("America/Toronto"))
        self.assertEqual(milliseconds_until_next_midnight(now), 30 * 60 * 1_000)

    def test_next_midnight_accounts_for_daylight_saving_time(self):
        now = datetime(2026, 11, 1, 0, 30, tzinfo=ZoneInfo("America/Toronto"))
        self.assertEqual(milliseconds_until_next_midnight(now), 24.5 * 60 * 60 * 1_000)


if __name__ == "__main__":
    unittest.main()
