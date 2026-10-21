from datetime import date, datetime, time, timedelta, timezone
import json
from pathlib import Path
import random
import unicodedata

from astral import Observer
from astral.sun import sunrise, sunset
import discord

from .config import Config
from .observances import occasion_for

ROOT = Path(__file__).resolve().parent.parent
DAYS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
MONTHS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre")
WISHES = (
    ("Bon courage pour cette nouvelle semaine ! Que votre lundi soit rempli d'énergie et de bonne humeur !", "Un nouveau lundi, de nouvelles possibilités : avancez à votre rythme et gardez le sourire !"),
    ("Très bon mardi, plein de sourires, de réussite et de bonnes nouvelles !", "Que ce mardi vous réserve de petites joies et de belles rencontres !"),
    ("Bon mercredi à toutes et à tous ! On garde le sourire, le week-end approche doucement ! 😄", "Déjà le milieu de semaine : prenez soin de vous et profitez de ce mercredi !"),
    ("Excellent jeudi ! Que vos projets avancent et que la bonne humeur vous accompagne !", "Un petit effort, une grande satisfaction : passez un beau jeudi !"),
    ("Bon courage pour cette dernière journée de la semaine et profitez bien de votre week-end !", "Courage pour ce vendredi ! Encore un peu de bonne humeur avant de profiter du week-end !"),
    ("Profitez pleinement de votre samedi, reposez-vous et faites le plein de bons moments !", "Un beau samedi à tous, avec du repos et de petits plaisirs !"),
    ("Doux dimanche à tous ! Faites le plein de bons moments pour la semaine à venir !", "Que votre dimanche soit paisible et rempli de sourires !"),
)
SEASONAL_TEXTS = (
    (
        "❄️ Les journées d'hiver invitent à ralentir un peu. Une boisson chaude, un bon livre ou une discussion entre amis : à chacun son petit moment de douceur ! ☕💙",
        "🧣 Un petit bonjour peut réchauffer une journée d'hiver ! Prenons des nouvelles de ceux qui comptent pour nous. 💙",
        "☕ En hiver aussi, les petits plaisirs font les belles journées : une pause, un sourire et un peu de convivialité ! ❄️",
        "❄️ Et si l'on profitait de cette journée pour partager une recette, une musique ou un souvenir qui fait sourire ? 🎶💙",
    ),
    (
        "🌷 Le printemps invite à profiter des couleurs et des petits moments dehors. Une belle occasion de faire une pause et de regarder autour de soi ! 🌿",
        "🌱 Avec le printemps, les idées fleurissent aussi ! Quel petit projet vous ferait plaisir aujourd'hui ? 💚",
        "🌼 Une balade, quelques photos ou un café entre amis : les plaisirs les plus simples font parfois les meilleurs souvenirs ! ☕",
        "🌿 Profitons de cette journée pour partager un peu de bonne humeur et prendre des nouvelles de nos proches ! 🌸",
    ),
    (
        "🌞 L'été invite à savourer les petits moments : une promenade, une discussion entre amis ou une pause au calme. Profitez de ce qui vous fait du bien ! 💛",
        "🌻 Et si l'on gardait un peu de temps aujourd'hui pour une activité qui nous plaît ? Les petits plaisirs comptent aussi ! 💙",
        "🍉 Une idée de sortie, une recette à partager ou simplement un bonjour : faisons circuler la bonne humeur ! 🌞",
        "🌅 Prenons le temps d'apprécier un joli paysage ou un moment de calme. Parfois, quelques minutes suffisent pour se changer les idées ! 💛",
    ),
    (
        "🍂 Les journées raccourcissent en automne : c'est l'occasion de profiter d'un peu de douceur et de convivialité ! Une boisson chaude et un moment entre amis, ça fait toujours plaisir. ☕🍁",
        "🍁 L'automne nous offre de belles couleurs à admirer. Et si l'on prenait quelques minutes pour une promenade ou une jolie photo ? 📷🍂",
        "☕ Les soirées d'automne se prêtent aux petits plaisirs : un livre, un jeu ou une discussion entre amis. Quel est votre programme idéal ? 🍂💙",
        "🍂 Une recette réconfortante, une musique qu'on aime et un peu de temps pour soi : de quoi apporter de la douceur à cette journée d'automne ! 🎶🍁",
    ),
)
BOLD_CAPITALS = str.maketrans({chr(65 + i): chr(0x1D400 + i) for i in range(26)})


def safe(text: str) -> str:
    return discord.utils.escape_markdown(discord.utils.escape_mentions(text.replace("\n", " ")))


def marker(day: date) -> str:
    # Ancien pied de message, encore reconnu dans l'historique.
    return f"Bulletin du {day.isoformat()}"


def date_line(day: date) -> str:
    return f"📅 **Nous sommes le {DAYS[day.weekday()]} {day.day} {MONTHS[day.month - 1]} {day.year}**"


def heading(text: str) -> str:
    return unicodedata.normalize("NFD", text.upper()).translate(BOLD_CAPITALS)


def editorial(text: str) -> str:
    """Autoriser le gras éditorial, en protégeant toujours les mentions et le reste du Markdown."""
    lines = []
    for line in text.splitlines():
        parts = line.split("**")
        # Ne pas produire de gras non refermé si le calendrier contient une coquille.
        lines.append("**".join(safe(part) for part in parts) if len(parts) % 2 else safe(line))
    return "\n".join(lines)


def occasion(day: date) -> dict | None:
    data = json.loads((ROOT / "calendar.json").read_text(encoding="utf-8"))
    event = (data["dates"].get(day.isoformat()) or data["annual"].get(day.strftime("%m-%d"))
             or occasion_for(day))
    # Le thème mensuel est un rappel du lundi, pas le même bulletin tous les jours.
    return event or (data["months"].get(str(day.month)) if day.weekday() == 0 else None)


def clock_notice(day: date, zone) -> list[str]:
    def offset(on_day):
        return datetime.combine(on_day, time(12), zone).utcoffset()

    current = offset(day)
    tomorrow = offset(day + timedelta(days=1))
    if tomorrow != current:
        winter = tomorrow < current
        title = heading("ATTENTION : CHANGEMENT D'HEURE !")
        return [
            f"⏰ **・{title}** 🕰️",
            f"🌙 Cette nuit, nous passons à **l'heure {'d’hiver' if winter else 'd’été'}** !",
            "À 3h du matin, il sera 2h. Une heure de sommeil en plus ! 😴" if winter else
            "À 2h du matin, il sera 3h. Pensez à avancer vos horloges d'une heure ! ⏰",
        ]
    yesterday = offset(day - timedelta(days=1))
    if yesterday != current:
        winter = current < yesterday
        return [
            f"🕰️ **Nous sommes passés à l'heure {'d’hiver' if winter else 'd’été'} !**",
            "⏰ Cette nuit, à 3h du matin, il était 2h. Une heure de sommeil en plus ! 😴" if winter else
            "⏰ Cette nuit, à 2h du matin, il était 3h. Pensez à vérifier vos horloges !",
        ]
    return []


def render(config: Config, day: date, names: list[str] | None) -> str:
    observer = Observer(config.latitude, config.longitude)
    rise = sunrise(observer, date=day, tzinfo=config.timezone)
    setting = sunset(observer, date=day, tzinfo=config.timezone)
    minutes = round((setting.astimezone(timezone.utc) - rise.astimezone(timezone.utc)).total_seconds() / 60)
    lines = [
        f"🤖 **・{heading('BONJOUR À TOUS !')}** 🌞",
        "━━━━━━━━━━━━━━━━━━━━━━",
        date_line(day),
        *clock_notice(day, config.timezone),
        f"🌅 **Lever du soleil :** {rise:%Hh%M}",
        f"🌇 **Coucher du soleil :** {setting:%Hh%M}",
        f"⏳ **Durée du jour :** {minutes // 60}h{minutes % 60:02d}",
    ]
    event = occasion(day)
    if event:
        lines.extend([f"🌍 **・{heading(safe(event['title']))}**", editorial(event["text"])])
    else:
        texts = SEASONAL_TEXTS[(day.month % 12) // 3]
        lines.extend([f"🌍 **・{heading('LE PETIT MOT DU JOUR')}**", texts[day.toordinal() % len(texts)]])
    lines.append(f"🎉 **・{heading('FÊTE DU JOUR')}**")
    if names:
        # Le lien sur la fleur crédite Nominis sans ajouter de pied technique au bulletin.
        lines.append(f"[💐](<https://nominis.cef.fr>) Bonne fête aux **{safe(names[0])}** !")
    else:
        lines.append("💐 Le calendrier des prénoms est indisponible aujourd'hui.")
    # Choix stable par date pour garder le même aperçu après un redémarrage.
    wish = random.Random(day.isoformat()).choice(WISHES[day.weekday()])
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    if day.weekday() == 4:
        lines.append(f"🎉 **{heading('ENFIN VENDREDI !')}**")
    lines.extend([f"✨ {wish} 💙", "🤖 *Votre bot vous souhaite une excellente journée !* 🌞"])
    message = "\n".join(lines)
    if len(message.encode("utf-16-le")) // 2 > 2000:
        raise ValueError("Le bulletin dépasse la limite Discord de 2 000 caractères. Raccourcir calendar.json.")
    return message
