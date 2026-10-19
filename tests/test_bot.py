import asyncio
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

import aiohttp
import discord

from bonjour.config import load_config
from bonjour.content import marker, occasion, render
from bonjour.namedays import get_names, parse_names
from bonjour.state import State, single_instance
from bot import BulletinClient, find_bulletin

ROOT = Path(__file__).resolve().parent.parent


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.tmp.cleanup)
        self.config = replace(load_config(ROOT / "config.example.json", preview=True),
                              guild_id=123, channel_id=456, state_db=Path(self.tmp.name) / "state.db")
        self.state = State(self.config.state_db)
        self.addCleanup(self.state.close)

    def test_dst_dates_and_local_delivery_window(self):
        # Avant et après les deux changements d'heure de 2026.
        for day, utc_hour in ((date(2026, 3, 28), 7), (date(2026, 3, 29), 6),
                              (date(2026, 10, 24), 6), (date(2026, 10, 25), 7)):
            plan = self.state.plan(self.config, day)
            target = datetime.fromisoformat(plan["target"])
            self.assertEqual(target.astimezone(timezone.utc).hour, utc_hour)
            self.assertEqual(target.hour, 8)
            self.assertEqual(target.second, 0)

    def test_schedule_and_sent_status_survive_restart(self):
        day = date(2026, 10, 19)
        first = dict(self.state.plan(self.config, day))
        self.state.set_status(123, day, "sent", 999)
        other = State(self.config.state_db)
        try:
            next_plan = other.plan(self.config, day)
            self.assertEqual(first["target"], next_plan["target"])
            self.assertEqual(next_plan["status"], "sent")
            self.assertEqual(next_plan["message_id"], "999")
        finally:
            other.close()

    def test_configuration_edits_only_move_pending_delivery(self):
        day = date(2026, 10, 19)
        self.state.plan(self.config, day)
        changed = replace(self.config, channel_id=789)
        self.assertEqual(self.state.plan(changed, day)["channel"], "789")
        self.state.set_status(123, day, "sending")
        self.assertEqual(self.state.plan(self.config, day)["channel"], "789")

    def test_render_entire_leap_year_and_french_example(self):
        for offset in range(366):
            day = date(2028, 1, 1) + timedelta(days=offset)
            text = render(self.config, day, ["René"])
            self.assertLessEqual(len(text.encode("utf-16-le")) // 2, 2000)
            self.assertIn(marker(day), text)
        example = render(self.config, date(2026, 10, 19), ["René"])
        self.assertIn("lundi 19 octobre 2026", example)
        self.assertIn("Paris", example)
        self.assertIn("OCTOBRE ROSE", example)
        self.assertIn("**René**", example)
        self.assertIsNone(occasion(date(2026, 2, 3)))

    def test_no_invented_fete_on_missing_source(self):
        text = render(self.config, date(2026, 10, 19), None)
        self.assertIn("indisponible", text)
        self.assertNotIn("Bonne fête aux", text)

    def test_nominis_explicit_date_and_names(self):
        payload = {"response": {"query": {"jour": "19", "mois": "10", "annee": "2026"},
                                "prenoms": {"majeurs": {"René": {}, "Renée": {}}}}}
        self.assertEqual(parse_names(payload, date(2026, 10, 19)), ["René", "Renée"])
        with self.assertRaises(ValueError):
            parse_names(payload, date(2026, 10, 20))

    def test_invalid_ids_coords_and_timezone(self):
        raw = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
        path = Path(self.tmp.name) / "config.json"
        for field, value in (("guild_id", "abc"), ("timezone", "UTC")):
            data = {**raw, "guild_id": "123", "channel_id": "456", field: value}
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_config(path)
        raw.update(guild_id="123", channel_id="456", location={"name": "Paris", "latitude": 91, "longitude": 2})
        path.write_text(json.dumps(raw), encoding="utf-8")
        with self.assertRaises(ValueError):
            load_config(path)

    def test_single_instance_lock(self):
        with single_instance(self.config.state_db):
            with self.assertRaises(RuntimeError):
                with single_instance(self.config.state_db):
                    pass


class FakeChannel:
    def __init__(self, messages=()):
        self.messages = messages
        self.send = AsyncMock(return_value=SimpleNamespace(id=999))

    async def history(self, **kwargs):
        for message in self.messages:
            yield message


class SchedulerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.config = replace(load_config(ROOT / "config.example.json", preview=True),
                              guild_id=123, channel_id=456, state_db=Path(self.tmp.name) / "state.db")
        self.state = State(self.config.state_db)
        self.session = aiohttp.ClientSession()
        self.client = BulletinClient(self.config, self.state, self.session)
        self.client._connection.user = SimpleNamespace(id=42)
        self.day = date(2026, 10, 19)
        self.now = datetime(2026, 10, 19, 8, 59, 30, tzinfo=self.config.timezone)
        self.channel = FakeChannel()
        self.client.destination = AsyncMock(return_value=self.channel)
        self.names_patch = patch("bot.get_names", new=AsyncMock(return_value=["René"]))
        self.names_patch.start()
        # Simuler l'horloge, y compris la vérification juste avant l'envoi.
        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return self.now.astimezone(tz)
        self.clock_patch = patch("bot.datetime", FixedDateTime)
        self.clock_patch.start()

    async def asyncTearDown(self):
        self.clock_patch.stop()
        self.names_patch.stop()
        await self.client.close()
        await self.session.close()
        self.state.close()
        self.tmp.cleanup()

    async def test_send_then_restart_does_not_send_twice(self):
        await self.client.tick(self.now)
        await self.client.tick(self.now)
        self.channel.send.assert_awaited_once()
        self.assertEqual(self.state.plan(self.config, self.day)["status"], "sent")

    async def test_no_post_before_or_after_window(self):
        await self.client.tick(self.now.replace(hour=7))
        self.channel.send.assert_not_awaited()
        await self.client.tick(self.now.replace(hour=9))
        self.channel.send.assert_not_awaited()
        self.assertEqual(self.state.plan(self.config, self.day)["status"], "skipped")

    async def test_recover_crash_after_discord_accepted_message(self):
        self.state.plan(self.config, self.day)
        self.state.set_status(123, self.day, "sending")
        self.channel.messages = [SimpleNamespace(id=77, author=SimpleNamespace(id=42),
                                                content=f"Bonjour\n-# {marker(self.day)}",
                                                created_at=self.now)]
        await self.client.tick(self.now)
        self.channel.send.assert_not_awaited()
        self.assertEqual(self.state.plan(self.config, self.day)["message_id"], "77")

    async def test_uncertain_network_reply_never_blindly_retries(self):
        self.channel.send.side_effect = TimeoutError("réponse perdue")
        with self.assertLogs("botdujour", level="ERROR"):
            await self.client.tick(self.now)
            await self.client.tick(self.now)
        self.channel.send.assert_awaited_once()
        self.assertEqual(self.state.plan(self.config, self.day)["status"], "uncertain")

    async def test_cannot_read_history_means_no_send(self):
        with patch("bot.find_bulletin", new=AsyncMock(side_effect=RuntimeError("historique refusé"))):
            with self.assertRaises(RuntimeError):
                await self.client.tick(self.now)
        self.channel.send.assert_not_awaited()
        self.assertEqual(self.state.plan(self.config, self.day)["status"], "pending")

    async def test_cached_namedays_need_no_network(self):
        self.state.cache_names(self.day, ["René"])
        self.assertEqual(await get_names(None, self.state, self.day), ["René"])

    async def test_api_failure_still_allows_bulletin(self):
        fake_session = SimpleNamespace(get=lambda *a, **kw: (_ for _ in ()).throw(aiohttp.ClientError()))
        with self.assertLogs("bonjour.namedays", level="WARNING"):
            self.assertIsNone(await get_names(fake_session, self.state, self.day))


if __name__ == "__main__":
    unittest.main()
