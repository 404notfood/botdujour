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
class InactivityConfig:
    enabled: bool = True
    after_minutes: int = 120
    start: time = time(9)
    end: time = time(22)
    tone: str = "mixed"
    include_voice: bool = True


@dataclass(frozen=True)
class VoiceConfig:
    announce_joins: bool = True


@dataclass(frozen=True)
class MentionsConfig:
    enabled: bool = True
    channel_ids: tuple[int, ...] = ()
    cooldown_seconds: int = 30


@dataclass(frozen=True)
class GoodnightConfig:
    enabled: bool = True
    at: time = time(23, 30)


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
    inactivity: InactivityConfig = InactivityConfig()
    voice: VoiceConfig = VoiceConfig()
    mentions: MentionsConfig = MentionsConfig()
    goodnight: GoodnightConfig = GoodnightConfig()


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
        idle = raw.get("inactivity", {})
        if not isinstance(idle, dict) or not isinstance(idle.get("enabled", True), bool):
            raise ValueError("inactivity.enabled doit être true ou false.")
        minutes = idle.get("after_minutes", 120)
        if type(minutes) is not int or not 1 <= minutes <= 10080:
            raise ValueError("inactivity.after_minutes doit être un entier entre 1 et 10080.")
        idle_start = time.fromisoformat(idle.get("start", "09:00"))
        idle_end = time.fromisoformat(idle.get("end", "22:00"))
        if any(t.tzinfo or t.second or t.microsecond for t in (idle_start, idle_end)) or not time(4) <= idle_start < idle_end <= time(23):
            raise ValueError("La fenêtre inactivity doit être au format HH:MM, entre 04:00 et 23:00, dans la même journée.")
        tone = idle.get("tone", "mixed")
        if tone not in ("light", "dark", "mixed"):
            raise ValueError("inactivity.tone doit être light, dark ou mixed.")
        include_voice = idle.get("include_voice", True)
        if not isinstance(include_voice, bool):
            raise ValueError("inactivity.include_voice doit être true ou false.")
        idle_config = InactivityConfig(idle.get("enabled", True), minutes, idle_start, idle_end, tone, include_voice)
        voice = raw.get("voice", {})
        if not isinstance(voice, dict) or not isinstance(voice.get("announce_joins", True), bool):
            raise ValueError("voice.announce_joins doit être true ou false.")
        voice_config = VoiceConfig(voice.get("announce_joins", True))
        mentions = raw.get("mentions", {})
        if not isinstance(mentions, dict) or not isinstance(mentions.get("enabled", True), bool):
            raise ValueError("mentions.enabled doit être true ou false.")
        mention_channels = mentions.get("channel_ids", [])
        if not isinstance(mention_channels, list):
            raise ValueError("mentions.channel_ids doit être une liste d'identifiants de salons.")
        for channel_id in mention_channels:
            value = str(channel_id)
            if not value.isascii() or not value.isdigit() or not 0 < int(value) < 2**64:
                raise ValueError("Identifiant de salon invalide dans mentions.channel_ids.")
        cooldown = mentions.get("cooldown_seconds", 30)
        if type(cooldown) is not int or not 1 <= cooldown <= 3600:
            raise ValueError("mentions.cooldown_seconds doit être un entier entre 1 et 3600.")
        mention_config = MentionsConfig(mentions.get("enabled", True), tuple(int(i) for i in mention_channels), cooldown)
        goodnight = raw.get("goodnight", {})
        if not isinstance(goodnight, dict) or not isinstance(goodnight.get("enabled", True), bool):
            raise ValueError("goodnight.enabled doit être true ou false.")
        goodnight_at = time.fromisoformat(goodnight.get("time", "23:30"))
        if (goodnight_at.tzinfo or goodnight_at.second or goodnight_at.microsecond
                or goodnight_at < time(4)):
            raise ValueError("goodnight.time doit être au format HH:MM, entre 04:00 et 23:59.")
        goodnight_config = GoodnightConfig(goodnight.get("enabled", True), goodnight_at)
        return Config(*ids, zone, start, end, name.strip(), lat, lon, path.resolve().parent / db,
                      greeting_config, idle_config, voice_config, mention_config, goodnight_config)
    except (KeyError, TypeError, OSError, ValueError) as exc:
        raise ValueError(f"Configuration {path} invalide : {exc}") from exc
