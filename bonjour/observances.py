"""Journées ONU depuis une copie locale révisée du calendrier officiel."""
from calendar import monthrange
from datetime import date
from functools import lru_cache
import json
from pathlib import Path
import unicodedata

CALENDAR = Path(__file__).resolve().parent.parent / "un_calendar.json"


@lru_cache(maxsize=1)
def load_events() -> tuple[dict, ...]:
    return tuple(json.loads(CALENDAR.read_text(encoding="utf-8"))["events"])


def matches(event: dict, day: date) -> bool:
    if "date" in event:
        return day.isoformat() == event["date"]
    if day.month != event["month"]:
        return False
    if "interval" in event:
        if day.year < event["first_year"] or (day.year - event["first_year"]) % event["interval"]:
            return False
    if "weekday" in event:
        if day.weekday() != event["weekday"]:
            return False
        if event["occurrence"] == -1:
            return day.day + 7 > monthrange(day.year, day.month)[1]
        return (day.day - 1) // 7 + 1 == event["occurrence"]
    return day.day in event.get("days", [event.get("day")])


def events_for(day: date) -> list[dict]:
    return [event for event in load_events() if matches(event, day)]


def theme(name: str) -> tuple[str, str]:
    normalized = "".join(c for c in unicodedata.normalize("NFD", name.casefold())
                         if not unicodedata.combining(c))
    choices = (
        (("victim", "genocide", "holocauste", "esclavage", "terrorisme", "violence", "torture", "guerre", "disparu", "disparition", "souvenir", "mariage des enfants"),
         "🕊️", "Une pensée pour les personnes concernées et leurs proches. Cultivons la mémoire, le respect et la solidarité."),
        (("cancer", "sante", "maladie", "sida", "hepatite", "diabete", "paludisme", "tuberculose", "antimicrobien", "vaccination", "donneur de sang"),
         "💙", "Une occasion de sensibiliser, de soutenir les personnes concernées et de saluer celles et ceux qui les accompagnent."),
        (("handicap", "braille", "trisomie", "albinisme", "sourd", "langues des signes"),
         "🤝", "Faisons une place à chacun : l'écoute, l'accessibilité et le respect nous rapprochent."),
        (("enfant", "jeunesse", "jeunes", "education", "enseignant", "alphabetisation"),
         "📚", "Encourageons les découvertes, le partage des connaissances et les possibilités offertes à chacun !"),
        (("femme", "fille", "egalite", "discrimination", "droits", "racisme", "islamophobie"),
         "🤝", "Rappelons l'importance de l'égalité, de la dignité et du respect de chacun au quotidien."),
        (("foret", "eau", "ocean", "environnement", "terre", "glacier", "ozone", "dechet", "air pur", "lacs", "sols", "montagne", "secheresse", "desertification"),
         "🌿", "Prenons soin de notre planète : chaque geste pour préserver la nature compte. 🌍💚"),
        (("oiseau", "leopard", "panthere", "abeille", "thon", "markhor", "cheval", "vie sauvage", "biologique"),
         "🐾", "Mettons à l'honneur la richesse du vivant et la protection des espèces et de leurs habitats ! 🌍💚"),
        (("science", "spatial", "lune", "asteroide", "technologie", "tic", "statistique", "innovation"),
         "🔬", "Restons curieux : les découvertes et le partage des connaissances nous aident à mieux comprendre le monde !"),
        (("langue", "poesie", "livre", "jazz", "culture", "creativite", "philosophie", "patrimoine", "radio", "television"),
         "🎨", "Une belle occasion de découvrir, de créer et de partager ce qui nous inspire !"),
        (("sport", "football", "basket", "bicyclette", "yoga", "jeu", "fair-play"),
         "🏅", "Mettons à l'honneur le plaisir de partager un moment ensemble, dans le respect et la bonne humeur !"),
        (("paix", "amitie", "bonheur", "tolerance", "fraternite", "solidarite", "charite", "espoir", "vivre-ensemble"),
         "🕊️", "Un sourire, un peu d'écoute ou un geste d'entraide : faisons vivre ces valeurs autour de nous ! 💙"),
    )
    for keywords, emoji, text in choices:
        if any(keyword in normalized for keyword in keywords):
            return emoji, text
    return "🌍", "Prenons un moment pour découvrir cette initiative et son rôle dans notre vie quotidienne."


def occasion_for(day: date) -> dict | None:
    events = events_for(day)
    if not events:
        return None
    lines = []
    for event in events:
        emoji, message = theme(event["name"])
        intro = "Aujourd'hui débute la" if event.get("kind") == "week" else "Aujourd'hui :"
        lines.append(f"{emoji} {intro} **{event['name']}**. {message}")
    title = "JOURNÉES DU JOUR" if len(events) > 1 else (
        "SEMAINE INTERNATIONALE" if events[0].get("kind") == "week" else "JOURNÉE DU JOUR")
    return {"title": title, "text": "\n".join(lines), "source": [e["source"] for e in events]}
