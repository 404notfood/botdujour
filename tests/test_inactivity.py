from dataclasses import replace
from datetime import datetime, timedelta, timezone, time
import json
from pathlib import Path
import tempfile
import sqlite3
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

import aiohttp
import discord

from bonjour.config import GreetingsConfig, InactivityConfig, VoiceConfig, load_config
from bonjour.inactivity import ASCII, BINARY, DARK, LIGHT, TIME_PROMPTS, choose_prompt, is_due
from bonjour.state import State
from bot import BulletinClient

ROOT = Path(__file__).resolve().parent.parent


class InactivityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.config = replace(load_config(ROOT / "config.example.json", preview=True),
                              guild_id=123, channel_id=456, state_db=Path(self.tmp.name) / "state.db",
                              greetings=GreetingsConfig(False))
        self.now = datetime(2026, 10, 19, 12, tzinfo=self.config.timezone)
        self.state = State(self.config.state_db)
        self.session = aiohttp.ClientSession()
        self.client = BulletinClient(self.config, self.state, self.session)
        self.client.activity_needs_sync = False
        self.messages = []
        test = self
        class Channel:
            send = AsyncMock()
            async def history(self, **kwargs):
                for message in sorted(test.messages, key=lambda m: m.created_at):
                    if message.created_at > kwargs["after"]:
                        yield message
        self.channel = Channel()
        self.channel.send.return_value = SimpleNamespace(id=900, created_at=self.now)
        self.channel.send.side_effect = lambda *a, **kw: SimpleNamespace(id=900, created_at=self.now)
        self.client.destination = AsyncMock(return_value=self.channel)
        class FixedDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return test.now.astimezone(tz)
        self.clock = patch("bot.datetime", FixedDatetime)
        self.clock.start()

    async def asyncTearDown(self):
        self.clock.stop()
        await self.client.close()
        await self.session.close()
        self.state.close()
        self.tmp.cleanup()

    def seed(self, minutes=120):
        return self.state.activity(123, 456, self.now - timedelta(minutes=minutes))

    def message(self, message_id=1000, *, human=True, at=None, webhook=None, channel=456):
        return SimpleNamespace(id=message_id, created_at=at or self.now,
                               guild=SimpleNamespace(id=123), channel=SimpleNamespace(id=channel),
                               author=SimpleNamespace(id=88, bot=not human), webhook_id=webhook,
                               content="Un message humain", reply=AsyncMock())

    async def test_first_install_waits_full_delay(self):
        self.client.activity_needs_sync = True
        await self.client.inactivity_tick(self.now)
        self.channel.send.assert_not_awaited()
        self.now += timedelta(minutes=119)
        await self.client.inactivity_tick(self.now)
        self.channel.send.assert_not_awaited()
        self.now += timedelta(minutes=1)
        await self.client.inactivity_tick(self.now)
        self.channel.send.assert_awaited_once()

    async def test_repeats_every_two_hours_and_human_restarts_delay(self):
        self.seed()
        await self.client.inactivity_tick(self.now)
        self.now += timedelta(minutes=119)
        await self.client.inactivity_tick(self.now)
        self.channel.send.assert_awaited_once()
        self.now += timedelta(minutes=1)
        await self.client.inactivity_tick(self.now)
        self.assertEqual(self.channel.send.await_count, 2)
        self.now += timedelta(minutes=30)
        await self.client.on_message(self.message())
        self.now += timedelta(minutes=119)
        await self.client.inactivity_tick(self.now)
        self.assertEqual(self.channel.send.await_count, 2)
        self.now += timedelta(minutes=1)
        await self.client.inactivity_tick(self.now)
        self.assertEqual(self.channel.send.await_count, 3)

    async def test_bots_and_webhooks_do_not_restart_the_two_hour_delay(self):
        self.seed()
        await self.client.inactivity_tick(self.now)
        self.now += timedelta(minutes=1)
        await self.client.on_message(self.message(human=False))
        await self.client.on_message(self.message(message_id=1001, webhook=5))
        self.now += timedelta(minutes=119)
        await self.client.inactivity_tick(self.now)
        self.assertEqual(self.channel.send.await_count, 2)

    async def test_activity_tracking_does_not_require_greetings_or_content_intent(self):
        self.seed()
        await self.client.on_message(self.message())
        await self.client.inactivity_tick(self.now)
        self.channel.send.assert_not_awaited()
        self.assertFalse(self.client.intents.message_content)
        self.assertTrue(self.client.intents.guild_messages)

    async def test_other_channel_does_not_reset_silence(self):
        self.seed()
        await self.client.on_message(self.message(channel=789))
        await self.client.inactivity_tick(self.now)
        self.channel.send.assert_awaited_once()

    async def test_history_prevents_prompt_after_offline_human_message(self):
        self.seed(minutes=300)
        self.messages = [self.message(at=self.now - timedelta(minutes=10))]
        self.client.activity_needs_sync = True
        await self.client.inactivity_tick(self.now)
        self.channel.send.assert_not_awaited()
        self.assertEqual(self.state.activity(123, 456, self.now)["last_human_id"], "1000")

    async def test_unreadable_history_never_sends(self):
        self.seed()
        self.client.destination.side_effect = ValueError("Accès refusé")
        with self.assertRaises(ValueError):
            await self.client.inactivity_tick(self.now)
        self.channel.send.assert_not_awaited()

    async def test_reservation_survives_restart_then_resumes_after_delay(self):
        self.seed()
        await self.client.inactivity_tick(self.now)
        self.state.close()
        self.state = State(self.config.state_db)
        self.client.state = self.state
        self.client.activity_needs_sync = True
        self.now += timedelta(minutes=119)
        await self.client.inactivity_tick(self.now)
        self.channel.send.assert_awaited_once()
        self.now += timedelta(minutes=1)
        await self.client.inactivity_tick(self.now)
        self.assertEqual(self.channel.send.await_count, 2)

    async def test_human_activity_during_history_fetch_is_respected(self):
        self.seed()
        async def destination(channel_id):
            await self.client.on_message(self.message())
            return self.channel
        self.client.destination.side_effect = destination
        await self.client.inactivity_tick(self.now)
        self.channel.send.assert_not_awaited()

    async def test_uncertain_send_waits_full_delay_before_next_attempt(self):
        self.seed()
        self.channel.send.side_effect = TimeoutError("réponse perdue")
        with self.assertLogs("botdujour", level="ERROR"):
            await self.client.inactivity_tick(self.now)
        await self.client.inactivity_tick(self.now)
        self.channel.send.assert_awaited_once()
        self.now += timedelta(minutes=119)
        await self.client.inactivity_tick(self.now)
        self.channel.send.assert_awaited_once()
        self.now += timedelta(minutes=1)
        self.channel.send.side_effect = None
        await self.client.inactivity_tick(self.now)
        self.assertEqual(self.channel.send.await_count, 2)

    async def test_explicit_refusal_allows_retry_after_fix(self):
        self.seed()
        self.channel.send.side_effect = discord.Forbidden(SimpleNamespace(status=403, reason="Forbidden"), "Missing permissions")
        with self.assertLogs("botdujour", level="WARNING"):
            await self.client.inactivity_tick(self.now)
        self.channel.send.side_effect = None
        await self.client.inactivity_tick(self.now)
        self.assertEqual(self.channel.send.await_count, 2)

    async def test_no_prompt_outside_9_to_22_paris(self):
        self.seed(minutes=600)
        for hour in (8, 22, 23):
            self.now = self.now.replace(hour=hour)
            await self.client.inactivity_tick(self.now)
        self.channel.send.assert_not_awaited()
        self.now = self.now.replace(hour=9)
        await self.client.inactivity_tick(self.now)
        self.channel.send.assert_awaited_once()

    async def test_elapsed_duration_uses_utc_across_dst(self):
        # Le temps écoulé est calculé en UTC ; la plage autorisée reste en heure de Paris.
        self.config = replace(self.config, inactivity=InactivityConfig(start=time(4)))
        at = datetime(2026, 10, 25, 0, 30, tzinfo=timezone.utc)
        row = self.state.activity(123, 456, at)
        before = datetime(2026, 10, 25, 1, 59, tzinfo=timezone.utc)
        after = datetime(2026, 10, 25, 3, 0, tzinfo=timezone.utc)
        self.assertFalse(is_due(self.config, row, before))
        self.assertTrue(is_due(self.config, row, after))
        spring = self.state.activity(123, 789, datetime(2026, 3, 29, 0, 30, tzinfo=timezone.utc))
        self.assertFalse(is_due(self.config, spring, datetime(2026, 3, 29, 2, 0, tzinfo=timezone.utc)))

    async def test_stale_claim_cannot_override_recent_human_activity(self):
        row = self.seed()
        await self.client.on_message(self.message())
        self.assertFalse(self.state.claim_inactivity(123, 456, row, self.now, "test"))

    async def test_disabled_inactivity_does_nothing(self):
        self.client.config = replace(self.config, inactivity=InactivityConfig(enabled=False))
        await self.client.inactivity_tick(self.now)
        self.client.destination.assert_not_awaited()

    async def test_voice_invitation_uses_current_guild_and_preserves_joke_rotation(self):
        self.seed()
        with patch.object(self.client, "get_guild", return_value=object()) as get_guild, \
                patch("bot.append_voice_invitation", side_effect=lambda text, guild: text + "\nVocal : Alex") as invite:
            await self.client.inactivity_tick(self.now)
            first_joke = self.state.activity(123, 456, self.now)["last_prompt_text"]
            self.assertEqual(self.channel.send.call_args.args[0], first_joke + "\nVocal : Alex")
            get_guild.assert_called_once_with(123)
            self.assertNotIn("Alex", first_joke)
            self.now += timedelta(hours=2)
            await self.client.inactivity_tick(self.now)
            self.assertEqual(invite.call_count, 2)
            self.assertNotEqual(first_joke, self.state.activity(123, 456, self.now)["last_prompt_text"])
        mentions = self.channel.send.call_args.kwargs["allowed_mentions"]
        self.assertFalse(mentions.everyone or mentions.users or mentions.roles)

    async def test_voice_invitation_can_be_disabled(self):
        self.seed()
        self.client.config = replace(self.config, inactivity=InactivityConfig(include_voice=False))
        with patch("bot.append_voice_invitation") as invite:
            await self.client.inactivity_tick(self.now)
            invite.assert_not_called()
        text = self.channel.send.call_args.args[0]
        self.assertTrue(text in TIME_PROMPTS["noon"] or text.startswith("🍽️ Pause de midi\n"))

    async def test_voice_intent_is_only_requested_for_enabled_invitations(self):
        self.assertTrue(self.client.intents.voice_states)
        for idle in (InactivityConfig(include_voice=False), InactivityConfig(enabled=False)):
            client = BulletinClient(replace(self.config, inactivity=idle, voice=VoiceConfig(False)),
                                    self.state, self.session)
            try:
                self.assertFalse(client.intents.voice_states)
                self.assertFalse(client.intents.members)
            finally:
                await client.close()

    async def test_voice_arrival_announces_even_with_inactivity_disabled(self):
        self.client.config = replace(self.config, inactivity=InactivityConfig(enabled=False))
        member = SimpleNamespace(bot=False, guild=SimpleNamespace(id=123))
        before, after = SimpleNamespace(channel=None), SimpleNamespace(channel=object())
        with patch("bot.voice_arrival", return_value="Alex vient de rejoindre le vocal") as arrival:
            await self.client.on_voice_state_update(member, before, after)
            arrival.assert_called_once_with(member, after.channel)
        self.client.destination.assert_awaited_once_with(456)
        self.channel.send.assert_awaited_once()
        self.assertEqual(self.channel.send.call_args.args[0], "Alex vient de rejoindre le vocal")
        mentions = self.channel.send.call_args.kwargs["allowed_mentions"]
        self.assertFalse(mentions.everyone or mentions.roles or mentions.users)

    async def test_voice_arrivals_ignore_bots_other_guilds_departures_and_mute_changes(self):
        channel = object()
        cases = ((True, 123, None, channel), (False, 999, None, channel),
                 (False, 123, channel, None), (False, 123, channel, channel))
        with patch("bot.voice_arrival") as arrival:
            for bot, guild_id, before, after in cases:
                await self.client.on_voice_state_update(
                    SimpleNamespace(bot=bot, guild=SimpleNamespace(id=guild_id)),
                    SimpleNamespace(channel=before), SimpleNamespace(channel=after))
            arrival.assert_not_called()
        self.channel.send.assert_not_awaited()

    async def test_voice_moves_are_announced_but_filtered_channels_are_not(self):
        member = SimpleNamespace(bot=False, guild=SimpleNamespace(id=123))
        before, after = SimpleNamespace(channel=object()), SimpleNamespace(channel=object())
        with patch("bot.voice_arrival", return_value="Changement de vocal"):
            await self.client.on_voice_state_update(member, before, after)
        self.channel.send.assert_awaited_once()
        with patch("bot.voice_arrival", return_value=None):
            await self.client.on_voice_state_update(member, before, after)
        self.channel.send.assert_awaited_once()

    async def test_voice_arrivals_can_be_disabled_independently(self):
        self.client.config = replace(self.config, voice=VoiceConfig(False))
        with patch("bot.voice_arrival") as arrival:
            await self.client.on_voice_state_update(SimpleNamespace(bot=False, guild=SimpleNamespace(id=123)),
                                                    SimpleNamespace(channel=None), SimpleNamespace(channel=object()))
            arrival.assert_not_called()
        self.channel.send.assert_not_awaited()

    async def test_voice_arrival_intent_is_independent_of_inactivity(self):
        client = BulletinClient(replace(self.config, inactivity=InactivityConfig(enabled=False)),
                                self.state, self.session)
        try:
            self.assertTrue(client.intents.voice_states)
            self.assertFalse(client.intents.members)
        finally:
            await client.close()

    async def test_voice_arrival_failure_is_logged_without_retry(self):
        self.channel.send.side_effect = TimeoutError("réponse perdue")
        with patch("bot.voice_arrival", return_value="Arrivée en vocal"), \
                self.assertLogs("botdujour", level="ERROR"):
            await self.client.on_voice_state_update(SimpleNamespace(bot=False, guild=SimpleNamespace(id=123)),
                                                    SimpleNamespace(channel=None), SimpleNamespace(channel=object()))
        self.channel.send.assert_awaited_once()

    async def test_tone_banks_and_mentions(self):
        self.assertIn(choose_prompt("light"), LIGHT + ASCII + BINARY)
        self.assertIn(choose_prompt("dark"), DARK + ASCII + BINARY)
        self.assertIn(choose_prompt("mixed"), LIGHT + DARK + ASCII + BINARY)
        self.seed()
        await self.client.inactivity_tick(self.now)
        text = self.channel.send.call_args.args[0]
        self.assertTrue(text in TIME_PROMPTS["noon"] or text.startswith("🍽️ Pause de midi\n"))
        self.assertFalse(self.channel.send.call_args.kwargs["allowed_mentions"].everyone)

    async def test_consecutive_prompts_differ_even_after_restart(self):
        self.seed()
        await self.client.inactivity_tick(self.now)
        first = self.channel.send.call_args.args[0]
        self.state.close()
        self.state = State(self.config.state_db)
        self.client.state = self.state
        self.client.activity_needs_sync = True
        self.now += timedelta(hours=2)
        await self.client.inactivity_tick(self.now)
        self.assertNotEqual(first, self.channel.send.call_args.args[0])

    async def test_binary_messages_decode_and_all_prompts_fit_discord(self):
        decoded = []
        for message in BINARY:
            bits = message.split("```text\n")[1].split("\n```")[0]
            decoded.append(bytes(int(byte, 2) for byte in bits.split()).decode("ascii"))
        self.assertIn("Bonjour les humains", decoded)
        for message in LIGHT + DARK + ASCII + BINARY:
            self.assertLessEqual(len(message.encode("utf-16-le")) // 2, 2000)
        for previous in LIGHT + DARK + ASCII + BINARY:
            self.assertNotEqual(choose_prompt("mixed", previous), previous)

    async def test_prompts_follow_local_time_preserve_tone_and_avoid_repetition(self):
        for hour, part, prefix in ((9, "morning", "☀️ Pause du matin"),
                                   (12, "noon", "🍽️ Pause de midi"),
                                   (15, "afternoon", "🍪 Pause de l'après-midi"),
                                   (20, "evening", "🌙 Pause du soir")):
            local = self.now.replace(hour=hour)
            for tone, bank in (("light", LIGHT), ("dark", DARK), ("mixed", LIGHT + DARK)):
                for previous in (None, TIME_PROMPTS[part][0], f"{prefix}\n{bank[0]}"):
                    with patch("bonjour.inactivity.secrets.choice", side_effect=lambda choices: choices[0]) as choose:
                        choose_prompt(tone, previous, local.astimezone(timezone.utc))
                    choices = choose.call_args.args[0]
                    self.assertNotIn(previous, choices)
                    for text in choices:
                        self.assertTrue(text in TIME_PROMPTS[part] or
                                        (text.startswith(prefix + "\n") and text.split("\n", 1)[1] in bank + ASCII + BINARY))
                        self.assertLessEqual(len(text.encode("utf-16-le")) // 2, 2000)

    async def test_no_night_catchup_burst(self):
        self.now = self.now.replace(hour=21)
        self.seed()
        await self.client.inactivity_tick(self.now)
        self.now += timedelta(hours=2)
        await self.client.inactivity_tick(self.now)
        self.channel.send.assert_awaited_once()
        self.now = (self.now + timedelta(days=1)).replace(hour=9)
        await self.client.inactivity_tick(self.now)
        await self.client.inactivity_tick(self.now)
        self.assertEqual(self.channel.send.await_count, 2)

    async def test_old_activity_schema_is_upgraded(self):
        path = Path(self.tmp.name) / "old.db"
        with sqlite3.connect(path) as db:
            db.execute("""CREATE TABLE channel_activity (guild TEXT, channel TEXT,
                last_message_at TEXT, last_human_at TEXT, last_human_id TEXT DEFAULT '0',
                prompted_for TEXT, PRIMARY KEY(guild,channel))""")
        db.close()
        old = State(path)
        try:
            row = old.activity(123, 456, self.now)
            self.assertIsNone(row["last_prompt_at"])
            self.assertIsNone(row["last_prompt_text"])
        finally:
            old.close()

    async def test_configuration_defaults_and_errors(self):
        raw = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
        raw.pop("inactivity")
        path = Path(self.tmp.name) / "config.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        self.assertEqual(load_config(path, preview=True).inactivity, InactivityConfig())
        for bad in ({"after_minutes": 0}, {"after_minutes": True}, {"enabled": "yes"},
                    {"tone": "autre"}, {"start": "22:00", "end": "09:00"}, {"start": "09:00+01:00"},
                    {"include_voice": "true"}, {"include_voice": 1}):
            raw["inactivity"] = bad
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_config(path, preview=True)
        raw["inactivity"] = {"include_voice": False}
        path.write_text(json.dumps(raw), encoding="utf-8")
        self.assertFalse(load_config(path, preview=True).inactivity.include_voice)

    async def test_voice_announcement_config_defaults_and_validation(self):
        raw = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
        raw.pop("voice")
        path = Path(self.tmp.name) / "voice-config.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        self.assertTrue(load_config(path, preview=True).voice.announce_joins)
        raw["voice"] = {"announce_joins": False}
        path.write_text(json.dumps(raw), encoding="utf-8")
        self.assertFalse(load_config(path, preview=True).voice.announce_joins)
        for invalid in (None, [], True, {"announce_joins": "true"}, {"announce_joins": 1}):
            raw["voice"] = invalid
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_config(path, preview=True)


if __name__ == "__main__":
    unittest.main()
