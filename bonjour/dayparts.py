"""Créneaux communs aux salutations et aux relances, en heure de Paris."""
from datetime import datetime
from zoneinfo import ZoneInfo


def daypart(now: datetime) -> str:
    hour = now.astimezone(ZoneInfo("Europe/Paris")).hour
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 14:
        return "noon"
    if 14 <= hour < 18:
        return "afternoon"
    return "evening"
