from dataclasses import dataclass
from datetime import time
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class GreetingsConfig:
    enabled: bool = True
    channel_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class Config:
    guild_id: int
    channel_id: int
    timezone: ZoneInfo
    start: time
    end: time
    location_name: str
    latitude: float
    longitude: float
    state_db: Path
    greetings: GreetingsConfig = GreetingsConfig()


def load_config(path: Path, *, preview: bool = False) -> Config:
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
        zone = ZoneInfo(raw["timezone"])
        if zone.key != "Europe/Paris":
            raise ValueError("Le fuseau doit être Europe/Paris.")
        start, end = (time.fromisoformat(raw["send_window"][k]) for k in ("start", "end"))
        if start.tzinfo or end.tzinfo or start.second or end.second or start.microsecond or end.microsecond:
            raise ValueError("Les heures doivent être au format HH:MM, sans fuseau.")
        if not time(4) <= start < end <= time(23):
            raise ValueError("La fenêtre doit rester dans la même journée, entre 04:00 et 23:00.")
        # Interdire les heures ambiguës ou inexistantes du changement d'heure.
        location = raw["location"]
        lat, lon = float(location["latitude"]), float(location["longitude"])
        if not math.isfinite(lat) or not math.isfinite(lon) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("Coordonnées géographiques invalides.")
        name = location["name"]
        if not isinstance(name, str) or not name.strip() or len(name) > 60:
            raise ValueError("Le nom de la ville doit contenir entre 1 et 60 caractères.")
        ids = []
        for key in ("guild_id", "channel_id"):
            value = str(raw[key])
            if preview and value.startswith("REMPLACER_"):
                ids.append(0)
            elif not value.isascii() or not value.isdigit() or not 0 < int(value) < 2**64:
                raise ValueError(f"{key} doit être un identifiant Discord numérique (copier l'identifiant).")
            else:
                ids.append(int(value))
        db = Path(raw.get("state_db", "data/bot.sqlite3"))
        greetings = raw.get("greetings", {})
        if not isinstance(greetings, dict) or not isinstance(greetings.get("enabled", True), bool):
            raise ValueError("greetings.enabled doit être true ou false.")
        channel_ids = greetings.get("channel_ids", [])
        if not isinstance(channel_ids, list):
            raise ValueError("greetings.channel_ids doit être une liste d'identifiants de salons.")
        for channel_id in channel_ids:
            value = str(channel_id)
            if not value.isascii() or not value.isdigit() or not 0 < int(value) < 2**64:
                raise ValueError("Identifiant de salon invalide dans greetings.channel_ids.")
        greeting_config = GreetingsConfig(greetings.get("enabled", True), tuple(int(i) for i in channel_ids))
        return Config(*ids, zone, start, end, name.strip(), lat, lon, path.resolve().parent / db, greeting_config)
    except (KeyError, TypeError, OSError, ValueError) as exc:
        raise ValueError(f"Configuration {path} invalide : {exc}") from exc
