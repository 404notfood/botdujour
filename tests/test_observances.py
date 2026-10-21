from datetime import date, timedelta
import unittest

from bonjour.observances import events_for, load_events, occasion_for
from scripts.update_un_calendar import parse_calendar


def names(on_day):
    return {event["name"] for event in events_for(on_day)}


class ObservanceTests(unittest.TestCase):
    def test_snapshot_covers_twelve_months_and_fixed_days(self):
        self.assertEqual({event.get("month") for event in load_events() if "month" in event}, set(range(1, 13)))
        self.assertGreater(len(load_events()), 200)
        self.assertIn("Journée mondiale du braille", names(date(2026, 1, 4)))
        self.assertNotIn("Journée mondiale du braille", names(date(2026, 1, 5)))
        self.assertIn("Journée mondiale de la méditation", names(date(2026, 12, 21)))

    def test_multiple_observances_are_kept_together(self):
        event = occasion_for(date(2026, 3, 21))
        for name in ("Journée internationale des forêts", "Journée mondiale de la poésie",
                     "Journée mondiale de la trisomie 21"):
            self.assertIn(f"**{name}**", event["text"])
        self.assertEqual(len(event["text"].splitlines()), len(events_for(date(2026, 3, 21))))

    def test_movable_observances_are_recomputed_for_each_year(self):
        for name, days in (
            ("Journée des jeunes filles dans le secteur des TIC", [date(2026, 4, 23), date(2027, 4, 22)]),
            ("Journée mondiale des oiseaux migrateurs", [date(2026, 5, 9), date(2026, 10, 10), date(2027, 5, 8)]),
            ("Journée internationale des coopératives", [date(2026, 7, 4), date(2027, 7, 3)]),
            ("Journée mondiale de la mer", [date(2026, 9, 24), date(2027, 9, 30)]),
            ("Journée mondiale de l'habitat", [date(2026, 10, 5), date(2027, 10, 4)]),
            ("Journée mondiale de la philosophie", [date(2026, 11, 19), date(2027, 11, 18)]),
            ("Journée mondiale du souvenir des victimes de la circulation routière", [date(2026, 11, 15), date(2027, 11, 21)]),
        ):
            for day in days:
                with self.subTest(name=name, day=day):
                    self.assertIn(name, names(day))
                    # Une date voisine garde le même thème de saison, mais pas cet événement.
                    self.assertNotIn(name, names(day + timedelta(days=1)))
        self.assertNotIn("Journée mondiale des oiseaux migrateurs", names(date(2026, 5, 11)))

    def test_statistics_is_not_declared_every_year(self):
        name = "Journée mondiale de la statistique"
        for year in (2010, 2025, 2030):
            self.assertIn(name, names(date(year, 10, 20)))
        for year in (2005, 2026, 2027, 2029):
            self.assertNotIn(name, names(date(year, 10, 20)))

    def test_lunar_date_is_not_reused_in_another_year(self):
        self.assertIn("Journée du Vesak", names(date(2026, 5, 1)))
        self.assertNotIn("Journée du Vesak", names(date(2027, 5, 1)))

    def test_week_opening_and_two_day_commemoration(self):
        self.assertIn("Semaine mondiale de l'espace", names(date(2026, 10, 4)))
        self.assertNotIn("Semaine mondiale de l'espace", names(date(2026, 10, 5)))
        for day in (8, 9):
            self.assertTrue(any("Seconde Guerre mondiale" in name for name in names(date(2026, 5, day))))
        science = events_for(date(2026, 11, 10))
        self.assertTrue(any(e["name"].startswith("Journée mondiale de la science") and e.get("kind") != "week"
                            for e in science))

    def test_import_refuses_incomplete_or_changed_source(self):
        with self.assertRaises(ValueError):
            parse_calendar("<html><title>Service indisponible</title></html>")
        with self.assertRaises(ValueError):
            parse_calendar('<div class="views-row views-row-1"><span>Nouvelle structure</span></div>')


if __name__ == "__main__":
    unittest.main()
