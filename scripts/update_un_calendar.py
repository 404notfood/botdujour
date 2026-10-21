"""Importer puis réviser localement le calendrier ONU, sans dépendance supplémentaire."""
import argparse
from datetime import date, datetime
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
SOURCE = "https://www.un.org/fr/observances/list-days-weeks"

# Les dates HTML des éditions précédentes ne sont pas des dates annuelles fixes.
# weekday : lundi = 0 ; occurrence = -1 signifie le dernier du mois.
MOVABLE = {
    "Journée des jeunes filles dans le secteur des TIC": (4, 3, 4, "https://www.itu.int/itu-d/sites/digital-inclusion-women-and-girls/home/girls-in-ict-day/"),
    "Journée mondiale des oiseaux migrateurs": (None, 5, 2, "https://www.worldmigratorybirdday.org/sites/default/files/wmbd_2025_may_summary_report.pdf"),
    "Journée internationale des coopératives": (7, 5, 1, "https://www.un.org/development/desa/cooperatives/2022/05/23/international-day-of-cooperatives-2022-cooperatives-build-a-better-world/"),
    "Journée mondiale de la mer": (9, 3, -1, "https://www.un.org/en/site-index/"),
    "Journée mondiale de l'habitat": (10, 0, 1, "https://www.un.org/observances/habitat-day"),
    "Journée mondiale de la philosophie": (11, 3, 3, "https://www.unesco.org/en/days/philosophy"),
    "Journée mondiale du souvenir des victimes de la circulation routière": (11, 6, 3, "https://www.un.org/en/un-chronicle/road-deaths-and-injuries-shatter-lives-impetus-lower-speeds-and-serious-post-crash"),
}


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, text):
        self.parts.append(text)


def parse_calendar(html: str) -> list[dict]:
    events = []
    for row in re.split(r'<div class="views-row\b[^>]*>', html)[1:]:
        title = re.search(r'<span class="views-field views-field-title">(.*?)</span>\s*</span>', row, re.S)
        stamp = re.search(r'property="dc:date"[^>]*content="(\d{4}-\d{2}-\d{2})T', row)
        if not title or not stamp:
            raise ValueError("Structure de ligne ONU inconnue : import interrompu, vérifier la page.")
        parser = PlainText()
        parser.feed(title[1])
        name = " ".join("".join(parser.parts).replace("\u200b", "").split())
        link = re.search(r'href="([^"]+)"', title[1])
        on_day = date.fromisoformat(stamp[1])
        event = {"name": name, "month": on_day.month, "day": on_day.day,
                 "source": urljoin(SOURCE, link[1]) if link else SOURCE}
        if name in MOVABLE:
            month, weekday, occurrence, rule_source = MOVABLE[name]
            event.pop("day")
            event.update(month=month or on_day.month, weekday=weekday,
                         occurrence=occurrence, rule_source=rule_source)
        elif name == "Journée mondiale de la statistique":
            event.update(first_year=2010, interval=5,
                         rule_source="https://www.un.org/en/observances/statistics-day")
        elif name == "Journée du Vesak":
            # Calendrier lunaire : ne jamais reconduire cette date une autre année.
            event.pop("month")
            event.pop("day")
            event["date"] = on_day.isoformat()
        elif name.startswith("Journées du souvenir et de la réconciliation"):
            event.pop("day")
            event["days"] = [8, 9]
        elif name.startswith("Semaine mondiale de la science"):
            event.update(name="Journée mondiale de la science au service de la paix et du développement",
                         source="https://www.unesco.org/fr/days/science-peace-development")
        elif name.startswith("Semaine mondiale pour un bon usage des antibiotiques"):
            event.update(name="Semaine mondiale d'information sur la résistance aux antimicrobiens",
                         day=18, source="https://www.who.int/fr/campaigns/world-antimicrobial-awareness-week")
        # Retirer les annotations éditoriales historiques du nom public.
        event["name"] = re.sub(r"\s*\[(?:UNESCO|OMS)\]|\s*\(2017\)", "", event["name"])
        event["name"] = event["name"].replace("crimede génocide", "crime de génocide")
        if event["name"].startswith("Semaine"):
            event["kind"] = "week"  # Annoncée à l'ouverture, sans répétition quotidienne.
        events.append(event)
    if len(events) < 180 or {e.get("month", 5) for e in events} != set(range(1, 13)):
        raise ValueError("Calendrier ONU incomplet : conserver le fichier précédent et vérifier la page.")
    return events


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", type=Path, help="Importer une copie locale de la page officielle.")
    parser.add_argument("--output", type=Path, default=ROOT / "un_calendar.json")
    parser.add_argument("--checked-on", type=date.fromisoformat,
                        default=datetime.now(ZoneInfo("Europe/Paris")).date())
    args = parser.parse_args()
    if args.html:
        html = args.html.read_text(encoding="utf-8")
    else:
        with urlopen(Request(SOURCE, headers={"User-Agent": "Mozilla/5.0 BotDuJour calendar import"}), timeout=25) as response:
            html = response.read().decode("utf-8")
    events = parse_calendar(html)
    payload = {"source": SOURCE, "checked_on": args.checked_on.isoformat(), "events": events}
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(events)} entrées importées dans {args.output}. Relire le diff avant utilisation.")


if __name__ == "__main__":
    main()
