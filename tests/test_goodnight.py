import asyncio
from dataclasses import replace
from datetime import datetime, time, timedelta, timezone
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from bonjour.config import GoodnightConfig, InactivityConfig, load_config
from bonjour.goodnight import REPLIES
from bonjour.state import State
from bot import BulletinClient

ROOT = Path(__file__).resolve().parent.parent


class GoodnightTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.config = replace(load_config(ROOT / "config.example.json", preview=True),
                              guild_id=123, channel_id=456, state_db=Path(self.tmp.name) / "state.db",
                              inactivity=InactivityConfig(enabled=False))
        self.state = State(self.config.state_db)
        self.client = BulletinClient(self.config, self.state, None)
        self.channel = SimpleNamespace(send=AsyncMock())
        self.client.destination = AsyncMock(return_value=self.channel)
        self.now = datetime(2026, 10, 25, 23, 30, tzinfo=self.config.timezone)
        test = self

        class FixedDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return test.now.astimezone(tz)

        self.clock = patch("bot.datetime", FixedDatetime)
        self.clock.start()

    async def asyncTearDown(self):
        self.clock.stop()
        await self.client.close()
        self.state.close()
        self.tmp.cleanup()

    async def test_not_before_2330_then_sends_once_even_with_inactivity_disabled(self):
        self.now -= timedelta(seconds=1)
        await self.client.goodnight_tick(self.now)
        self.client.destination.assert_not_awaited()
        self.now += timedelta(seconds=1)
        await asyncio.gather(self.client.goodnight_tick(self.now), self.client.goodnight_tick(self.now))
        self.client.destination.assert_awaited_with(456)
        self.channel.send.assert_awaited_once()
        self.assertIn(self.channel.send.call_args.args[0], REPLIES)
        mentions = self.channel.send.call_args.kwargs["allowed_mentions"]
        self.assertFalse(mentions.everyone or mentions.roles or mentions.users)

    async def test_restart_preserves_reservation_but_next_evening_can_send(self):
        await self.client.goodnight_tick(self.now)
        self.state.close()
        self.state = State(self.config.state_db)
        self.client.state = self.state
        await self.client.goodnight_tick(self.now)
        self.channel.send.assert_awaited_once()
        self.now += timedelta(days=1)
        await self.client.goodnight_tick(self.now)
        self.assertEqual(self.channel.send.await_count, 2)

    async def test_paris_schedule_in_winter_summer_and_after_clock_change(self):
        for month, utc_hour in ((1, 22), (7, 21), (10, 22)):
            with self.subTest(month=month):
                self.now = datetime(2026, month, 25, utc_hour, 29, 59, tzinfo=timezone.utc)
                previous = self.channel.send.await_count
                await self.client.goodnight_tick(self.now)
                self.assertEqual(self.channel.send.await_count, previous)
                self.now += timedelta(seconds=1)
                await self.client.goodnight_tick(self.now)
                self.assertEqual(self.channel.send.await_count, previous + 1)

    async def test_late_start_before_midnight_sends_without_morning_catchup(self):
        self.now = self.now.replace(hour=23, minute=59)
        await self.client.goodnight_tick(self.now)
        self.now += timedelta(minutes=1)
        await self.client.goodnight_tick(self.now)
        self.now = self.now.replace(hour=8)
        await self.client.goodnight_tick(self.now)
        self.channel.send.assert_awaited_once()

    async def test_network_wait_crossing_midnight_prevents_stale_send(self):
        async def destination(channel_id):
            self.now = (self.now + timedelta(days=1)).replace(hour=0, minute=0)
            return self.channel

        self.client.destination.side_effect = destination
        await self.client.goodnight_tick(self.now)
        self.channel.send.assert_not_awaited()

    async def test_disabled_or_custom_hour(self):
        self.client.config = replace(self.config, goodnight=GoodnightConfig(enabled=False))
        await self.client.goodnight_tick(self.now)
        self.client.destination.assert_not_awaited()
        self.client.config = replace(self.config, goodnight=GoodnightConfig(at=time(23, 45)))
        await self.client.goodnight_tick(self.now)
        self.channel.send.assert_not_awaited()
        self.now = self.now.replace(minute=45)
        await self.client.goodnight_tick(self.now)
        self.channel.send.assert_awaited_once()

    async def test_explicit_refusal_can_retry_but_uncertain_send_cannot(self):
        self.channel.send.side_effect = discord.Forbidden(SimpleNamespace(status=403, reason="Forbidden"), "Missing permissions")
        with self.assertLogs("botdujour", level="WARNING"):
            await self.client.goodnight_tick(self.now)
        self.assertFalse(self.state.has_goodnight(123, self.now.date()))
        self.channel.send.side_effect = TimeoutError("réponse perdue")
        with self.assertLogs("botdujour", level="ERROR"):
            await self.client.goodnight_tick(self.now)
        await self.client.goodnight_tick(self.now)
        self.assertEqual(self.channel.send.await_count, 2)

    async def test_scheduler_checks_goodnight_even_when_morning_bulletin_fails(self):
        self.client.wait_until_ready = AsyncMock()
        self.client.is_closed = Mock(side_effect=[False, True])
        self.client.is_ready = Mock(return_value=True)
        self.client.tick = AsyncMock(side_effect=RuntimeError("bulletin indisponible"))
        self.client.inactivity_tick = AsyncMock()
        self.client.goodnight_tick = AsyncMock()
        with patch("bot.asyncio.sleep", new=AsyncMock()), self.assertLogs("botdujour", level="ERROR"):
            await self.client.scheduler()
        self.client.goodnight_tick.assert_awaited_once_with(self.now)

    def test_goodnight_configuration_is_optional_and_validated(self):
        raw = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
        raw.pop("goodnight")
        path = Path(self.tmp.name) / "config.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        self.assertEqual(load_config(path, preview=True).goodnight, GoodnightConfig())
        for invalid in (None, [], {"enabled": 1}, {"time": None}, {"time": "25:00"},
                        {"time": "02:30"}, {"time": "23:30:01"}, {"time": "23:30+01:00"}):
            raw["goodnight"] = invalid
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                load_config(path, preview=True)
        raw["goodnight"] = {"enabled": False, "time": "23:45"}
        path.write_text(json.dumps(raw), encoding="utf-8")
        self.assertEqual(load_config(path, preview=True).goodnight, GoodnightConfig(False, time(23, 45)))

    def test_all_goodnight_messages_fit_discord(self):
        self.assertEqual(len(REPLIES), len(set(REPLIES)))
        self.assertTrue(any("aquaponey sur la Lune" in text for text in REPLIES))
        for text in REPLIES:
            self.assertLessEqual(len(text.encode("utf-16-le")) // 2, 2000)


if __name__ == "__main__":
    unittest.main()
