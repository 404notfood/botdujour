from datetime import date, timezone
import json
from pathlib import Path
import random

from astral import Observer
from astral.sun import sunrise, sunset
import discord

from .config import Config

ROOT = Path(__file__).resolve().parent.parent
DAYS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
MONTHS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre")
WISHES = (
    ("Bon courage pour cette nouvelle semaine ! Que votre lundi soit rempli d'énergie et de bonne humeur !", "Un nouveau lundi, de nouvelles possibilités : avancez à votre rythme et gardez le sourire !"),
    ("Très bon mardi, plein de sourires, de réussite et de bonnes nouvelles !", "Que ce mardi vous réserve de petites joies et de belles rencontres !"),
    ("Bon mercredi ! Une petite pause, un sourire, et on repart du bon pied !", "Déjà le milieu de semaine : prenez soin de vous et profitez de ce mercredi !"),
    ("Excellent jeudi ! Que vos projets avancent et que la bonne humeur vous accompagne !", "Un petit effort, une grande satisfaction : passez un beau jeudi !"),
    ("Bon vendredi à tous ! On termine la semaine avec le sourire !", "Courage pour ce vendredi, le week-end approche !"),
    ("Bon samedi ! Profitez d'un moment pour vous et pour les personnes que vous aimez !", "Un beau samedi à tous, avec du repos et de petits plaisirs !"),
    ("Doux dimanche à tous ! Faites le plein de bons moments pour la semaine à venir !", "Que votre dimanche soit paisible et rempli de sourires !"),
)


def safe(text: str) -> str:
    return discord.utils.escape_markdown(discord.utils.escape_mentions(text.replace("\n", " ")))


def marker(day: date) -> str:
    return f"Bulletin du {day.isoformat()}"


def occasion(day: date) -> dict | None:
    data = json.loads((ROOT / "calendar.json").read_text(encoding="utf-8"))
    return (data["dates"].get(day.isoformat()) or data["annual"].get(day.strftime("%m-%d"))
            or data["months"].get(str(day.month)))


def render(config: Config, day: date, names: list[str] | None) -> str:
    observer = Observer(config.latitude, config.longitude)
    rise = sunrise(observer, date=day, tzinfo=config.timezone)
    setting = sunset(observer, date=day, tzinfo=config.timezone)
    minutes = round((setting.astimezone(timezone.utc) - rise.astimezone(timezone.utc)).total_seconds() / 60)
    lines = [
        "🤖 **・𝐁𝐎𝐍𝐉𝐎𝐔𝐑 À 𝐓𝐎𝐔𝐒 !** 🌞",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"📅 **Nous sommes le {DAYS[day.weekday()]} {day.day} {MONTHS[day.month - 1]} {day.year}**",
        f"📍 **Soleil : {safe(config.location_name)}** · heure de Paris",
        f"🌅 **Lever du soleil :** {rise:%Hh%M}",
        f"🌇 **Coucher du soleil :** {setting:%Hh%M}",
        f"⏳ **Durée du jour :** {minutes // 60}h{minutes % 60:02d}",
    ]
    event = occasion(day)
    if event:
        lines.extend(["", f"🌍 **・{safe(event['title'])}**", safe(event["text"])])
    lines.extend(["", "🎉 **・𝐅Ê𝐓𝐄 𝐃𝐔 𝐉𝐎𝐔𝐑**"])
    if names:
        lines.append(f"💐 Bonne fête aux **{', '.join(safe(n) for n in names[:6])}** !")
    else:
        lines.append("💐 Le calendrier des prénoms est indisponible aujourd'hui.")
    # Choix stable par date pour garder le même aperçu après un redémarrage.
    wish = random.Random(day.isoformat()).choice(WISHES[day.weekday()])
    lines.extend(["━━━━━━━━━━━━━━━━━━━━━━", f"✨ {wish} 💙",
                  "🤖 *Votre bot vous souhaite une excellente journée !* 🌞",
                  f"-# {marker(day)}" + (" · Fêtes : <https://nominis.cef.fr>" if names else "")])
    message = "\n".join(lines)
    if len(message.encode("utf-16-le")) // 2 > 2000:
        raise ValueError("Le bulletin dépasse la limite Discord de 2 000 caractères. Raccourcir calendar.json.")
    return message
