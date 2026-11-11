"""Match-day fixes: TBA keys, duplicate block, add-form redirects, edit identity and exclusion.

MongoDB is never contacted: managers are built with __new__ and a MagicMock db."""
import unittest

from app.scout.match13_fuel import match_key
from app.scout.TBA import tba_match_key


class MatchKeyTests(unittest.TestCase):
    def test_labels_map_to_tba_keys_in_any_year(self):
        self.assertEqual(tba_match_key("2027nyny", "Qual 12"), "2027nyny_qm12")
        self.assertEqual(tba_match_key("2027nyny", "Semifinal 2-1"), "2027nyny_sf2m1")
        self.assertEqual(tba_match_key("2027nyny", "Final 2"), "2027nyny_f1m2")
        self.assertEqual(tba_match_key("2026test1", "Qual 3"), "2026test1_qm3")
        self.assertEqual(tba_match_key("2027nyny", "2027nyny_qm3"), "2027nyny_qm3")

    def test_bad_event_or_label_gives_none(self):
        for event, label in [("nyny", "Qual 1"), ("", "Qual 1"), ("2027NYNY", "Qual 1"),
                             ("2027nyny", "Practice 1"), ("2027nyny", ""), ("2027nyny", "2026other_qm1")]:
            self.assertIsNone(tba_match_key(event, label), (event, label))

    def test_match13_stays_2026_only(self):
        self.assertIsNone(match_key("2027nyny", "Qual 1"))
        self.assertEqual(match_key("2026nyny", "Qual 1"), "2026nyny_qm1")


if __name__ == '__main__':
    unittest.main()
