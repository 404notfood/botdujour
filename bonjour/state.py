from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import secrets
import sqlite3

from .config import Config


@contextmanager
def single_instance(db_path: Path):
    """Verrou OS libéré même si le processus est tué."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    handle = db_path.with_suffix(".lock").open("a+b")
    try:
        import os
        if os.name == "nt":
            import msvcrt
            handle.seek(0)
            if not handle.read(1):
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        raise RuntimeError("Une autre instance utilise déjà cette base de données.") from None
    try:
        yield
    finally:
        handle.close()


class State:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS deliveries (
                guild TEXT NOT NULL, day TEXT NOT NULL, target TEXT NOT NULL,
                channel TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
                message_id TEXT, PRIMARY KEY (guild, day)
            );
            CREATE TABLE IF NOT EXISTS namedays (day TEXT PRIMARY KEY, names TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS greetings (
                guild TEXT NOT NULL, day TEXT NOT NULL, user TEXT NOT NULL,
                PRIMARY KEY (guild, day, user)
            );
            CREATE TABLE IF NOT EXISTS mention_replies (
                guild TEXT NOT NULL, user TEXT NOT NULL, replied_at TEXT NOT NULL,
                PRIMARY KEY (guild, user)
            );
            CREATE TABLE IF NOT EXISTS goodnights (
                guild TEXT NOT NULL, day TEXT NOT NULL,
                PRIMARY KEY (guild, day)
            );
            CREATE TABLE IF NOT EXISTS channel_activity (
                guild TEXT NOT NULL, channel TEXT NOT NULL,
                last_message_at TEXT NOT NULL, last_human_at TEXT NOT NULL,
                last_human_id TEXT NOT NULL DEFAULT '0',
                last_prompt_at TEXT, last_prompt_text TEXT, PRIMARY KEY (guild, channel)
            );
        """)
        # Compatibilité avec une base ayant déjà utilisé la première version des relances.
        columns = {r[1] for r in self.db.execute("PRAGMA table_info(channel_activity)")}
        for column in ("last_prompt_at", "last_prompt_text"):
            if column not in columns:
                with self.db:
                    self.db.execute(f"ALTER TABLE channel_activity ADD COLUMN {column} TEXT")

    def close(self):
        self.db.close()

    def plan(self, config: Config, day: date):
        start = datetime.combine(day, config.start, config.timezone)
        end = datetime.combine(day, config.end, config.timezone)
        target = start + timedelta(minutes=secrets.randbelow(int((end - start).total_seconds() // 60)))
        with self.db:
            self.db.execute(
                "INSERT OR IGNORE INTO deliveries (guild,day,target,channel) VALUES (?,?,?,?)",
                (str(config.guild_id), day.isoformat(), target.isoformat(), str(config.channel_id)),
            )
        row = self.db.execute("SELECT * FROM deliveries WHERE guild=? AND day=?",
                              (str(config.guild_id), day.isoformat())).fetchone()
        if row["status"] == "pending":
            saved = datetime.fromisoformat(row["target"]).astimezone(config.timezone)
            # Appliquer une modification de configuration avant l'envoi uniquement.
            new_target = row["target"] if start <= saved < end else target.isoformat()
            with self.db:
                self.db.execute("UPDATE deliveries SET target=?,channel=? WHERE guild=? AND day=?",
                                (new_target, str(config.channel_id), str(config.guild_id), day.isoformat()))
            row = self.db.execute("SELECT * FROM deliveries WHERE guild=? AND day=?",
                                  (str(config.guild_id), day.isoformat())).fetchone()
        return row

    def set_status(self, guild: int, day: date, status: str, message_id=None):
        with self.db:
            self.db.execute("UPDATE deliveries SET status=?,message_id=? WHERE guild=? AND day=?",
                            (status, str(message_id) if message_id else None, str(guild), day.isoformat()))

    def cached_names(self, day: date):
        import json
        row = self.db.execute("SELECT names FROM namedays WHERE day=?", (day.isoformat(),)).fetchone()
        return json.loads(row[0]) if row else None

    def has_goodnight(self, guild: int, day: date) -> bool:
        return self.db.execute("SELECT 1 FROM goodnights WHERE guild=? AND day=?",
                               (str(guild), day.isoformat())).fetchone() is not None

    def claim_goodnight(self, guild: int, day: date) -> bool:
        with self.db:
            cursor = self.db.execute("INSERT OR IGNORE INTO goodnights (guild,day) VALUES (?,?)",
                                     (str(guild), day.isoformat()))
        return cursor.rowcount == 1

    def release_goodnight(self, guild: int, day: date):
        """Libérer uniquement si Discord confirme le refus de l'envoi."""
        with self.db:
            self.db.execute("DELETE FROM goodnights WHERE guild=? AND day=?", (str(guild), day.isoformat()))

    def cache_names(self, day: date, names: list[str]):
        import json
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO namedays VALUES (?,?)", (day.isoformat(), json.dumps(names)))

    def claim_greeting(self, guild: int, day: date, user: int) -> bool:
        """Réserver avant l'envoi : une réponse par personne et par jour, tous salons confondus."""
        with self.db:
            cursor = self.db.execute("INSERT OR IGNORE INTO greetings (guild,day,user) VALUES (?,?,?)",
                                     (str(guild), day.isoformat(), str(user)))
        return cursor.rowcount == 1

    def release_greeting(self, guild: int, day: date, user: int):
        """À utiliser seulement quand Discord confirme qu'aucun message n'a été envoyé."""
        with self.db:
            self.db.execute("DELETE FROM greetings WHERE guild=? AND day=? AND user=?",
                            (str(guild), day.isoformat(), str(user)))

    def activity(self, guild: int, channel: int, now: datetime):
        # Au premier lancement, commencer un délai complet plutôt que publier immédiatement.
        with self.db:
            timestamp = now.astimezone(timezone.utc).isoformat()
            self.db.execute("INSERT OR IGNORE INTO channel_activity (guild,channel,last_message_at,last_human_at) VALUES (?,?,?,?)",
                            (str(guild), str(channel), timestamp, timestamp))
        return self.db.execute("SELECT * FROM channel_activity WHERE guild=? AND channel=?",
                               (str(guild), str(channel))).fetchone()

    def claim_mention(self, guild: int, user: int, now: datetime, cooldown_seconds: int) -> bool:
        """Réserver atomiquement une réponse, tous salons confondus, même après redémarrage."""
        utc = now.astimezone(timezone.utc)
        cutoff = (utc - timedelta(seconds=cooldown_seconds)).isoformat()
        with self.db:
            cursor = self.db.execute("""INSERT INTO mention_replies (guild,user,replied_at) VALUES (?,?,?)
                ON CONFLICT(guild,user) DO UPDATE SET replied_at=excluded.replied_at
                WHERE mention_replies.replied_at <= ?""",
                (str(guild), str(user), utc.isoformat(), cutoff))
        return cursor.rowcount == 1

    def release_mention(self, guild: int, user: int, reserved_at: datetime):
        with self.db:
            self.db.execute("DELETE FROM mention_replies WHERE guild=? AND user=? AND replied_at=?",
                            (str(guild), str(user), reserved_at.astimezone(timezone.utc).isoformat()))

    def observe_activity(self, guild: int, channel: int, message_id: int, at: datetime, *, human: bool):
        row = self.activity(guild, channel, at)
        human_id = str(max(int(row["last_human_id"]), message_id)) if human else row["last_human_id"]
        human_at = max(datetime.fromisoformat(row["last_human_at"]), at.astimezone(timezone.utc)).isoformat() if human else row["last_human_at"]
        latest = max(datetime.fromisoformat(row["last_message_at"]), at.astimezone(timezone.utc)).isoformat()
        with self.db:
            self.db.execute("UPDATE channel_activity SET last_message_at=?,last_human_at=?,last_human_id=? WHERE guild=? AND channel=?",
                            (latest, human_at, human_id, str(guild), str(channel)))

    def claim_inactivity(self, guild: int, channel: int, row, now: datetime, text: str) -> bool:
        with self.db:
            cursor = self.db.execute("""UPDATE channel_activity SET last_prompt_at=?,last_prompt_text=?
                WHERE guild=? AND channel=? AND last_human_id=? AND last_message_at=?
                AND last_prompt_at IS ?""",
                (now.astimezone(timezone.utc).isoformat(), text, str(guild), str(channel),
                 row["last_human_id"], row["last_message_at"], row["last_prompt_at"]))
        return cursor.rowcount == 1

    def release_inactivity(self, guild: int, channel: int, reserved_at: datetime, previous):
        with self.db:
            self.db.execute("""UPDATE channel_activity SET last_prompt_at=?,last_prompt_text=?
                WHERE guild=? AND channel=? AND last_prompt_at=?""",
                (previous["last_prompt_at"], previous["last_prompt_text"], str(guild), str(channel),
                 reserved_at.astimezone(timezone.utc).isoformat()))

    def complete_inactivity(self, guild: int, channel: int, reserved_at: datetime, sent_at: datetime):
        with self.db:
            self.db.execute("UPDATE channel_activity SET last_prompt_at=? WHERE guild=? AND channel=? AND last_prompt_at=?",
                            (sent_at.astimezone(timezone.utc).isoformat(), str(guild), str(channel),
                             reserved_at.astimezone(timezone.utc).isoformat()))
