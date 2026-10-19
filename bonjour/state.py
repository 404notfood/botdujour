from contextlib import contextmanager
from datetime import date, datetime, timedelta
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
        """)

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

    def cache_names(self, day: date, names: list[str]):
        import json
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO namedays VALUES (?,?)", (day.isoformat(), json.dumps(names)))
