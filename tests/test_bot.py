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

from bonjour.config import GreetingsConfig, MentionsConfig, InactivityConfig, load_config
from bonjour.content import SEASONAL_TEXTS, clock_notice, date_line, editorial, marker, occasion, render, seasonal_text
from bonjour.greetings import is_greeting, make_reply
from bonjour.dayparts import daypart
from bonjour.mentions import is_direct_mention
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
            self.assertIn(date_line(day), text)
            self.assertIn("🌍", text)
        example = render(self.config, date(2026, 10, 19), ["René"])
        self.assertIn("lundi 19 octobre 2026", example)
        self.assertNotIn("📍", example)
        self.assertNotIn("-# Bulletin du", example)
        self.assertIn("Octobre rose", example)
        self.assertIn("**René**", example)
        self.assertIsNone(occasion(date(2026, 2, 3)))

    def test_calendar_changes_between_days_and_preserves_event_formatting(self):
        monday = render(self.config, date(2026, 10, 19), ["René"])
        tuesday = render(self.config, date(2026, 10, 20), ["Adeline"])
        wednesday = render(self.config, date(2026, 10, 21), ["Céline", "Ursule"])
        self.assertIn("Octobre rose", monday)
        self.assertNotIn("Octobre rose", tuesday + wednesday)
        self.assertIn("**Journée mondiale de l'ostéoporose**", tuesday)
        self.assertIn("**Céline**", wednesday)
        self.assertNotIn("Ursule", wednesday)
        self.assertIn("https://nominis.cef.fr", wednesday)
        self.assertNotIn(r"\*", wednesday)
        # Une journée annuelle reste prioritaire même lorsqu'elle tombe un lundi.
        self.assertIn("bégaiement", occasion(date(2029, 10, 22))["text"])

    def test_missing_days_receive_distinct_stable_texts(self):
        for year in (2026, 2027, 2028):
            chosen = [[], [], [], []]
            day = date(year, 1, 1)
            while day.year == year:
                if occasion(day) is None:
                    text = seasonal_text(day)
                    self.assertEqual(text, seasonal_text(day))
                    season = (day.month % 12) // 3
                    self.assertIn(text, SEASONAL_TEXTS[season])
                    chosen[season].append(text)
                day += timedelta(days=1)
            for season, texts in enumerate(chosen):
                with self.subTest(year=year, season=season):
                    self.assertLessEqual(len(texts), len(SEASONAL_TEXTS[season]))
                    self.assertEqual(len(texts), len(set(texts)))

    def test_humorous_text_is_only_used_without_an_event(self):
        missing = date(2026, 10, 21)
        self.assertIn(editorial(seasonal_text(missing)), render(self.config, missing, ["Céline"]))
        official = render(self.config, date(2026, 10, 27), ["Émeline"])
        self.assertIn("Journée mondiale du patrimoine audiovisuel", official)
        self.assertNotIn("𝐋𝐄 𝐏𝐄𝐓𝐈𝐓 𝐌𝐎𝐓 𝐃𝐔 𝐉𝐎𝐔𝐑", official)

    def test_editorial_bold_keeps_line_breaks_and_escapes_mentions(self):
        text = editorial("🕊️ **Une journée**\n@everyone _exemple_ <@123456789012345678>")
        self.assertIn("**Une journée**\n", text)
        self.assertIn("@\u200beveryone", text)
        self.assertIn("<@\u200b123456789012345678>", text)
        self.assertIn(r"\_exemple\_", text)
        self.assertEqual(editorial("**incomplet"), r"\*\*incomplet")

    def test_clock_notices_follow_paris_transitions_each_year(self):
        for transition, season, before, after in (
            (date(2026, 3, 29), "d’été", "À 2h du matin, il sera 3h", "à 2h du matin, il était 3h"),
            (date(2026, 10, 25), "d’hiver", "À 3h du matin, il sera 2h", "à 3h du matin, il était 2h"),
            (date(2027, 3, 28), "d’été", "À 2h du matin, il sera 3h", "à 2h du matin, il était 3h"),
            (date(2027, 10, 31), "d’hiver", "À 3h du matin, il sera 2h", "à 3h du matin, il était 2h"),
        ):
            with self.subTest(transition=transition):
                eve = "\n".join(clock_notice(transition - timedelta(days=1), self.config.timezone))
                today = "\n".join(clock_notice(transition, self.config.timezone))
                self.assertIn(season, eve)
                self.assertIn(before, eve)
                self.assertIn(season, today)
                self.assertIn(after, today)
                self.assertEqual(clock_notice(transition - timedelta(days=2), self.config.timezone), [])
                self.assertEqual(clock_notice(transition + timedelta(days=1), self.config.timezone), [])

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

    def test_greeting_detection(self):
        for text in ("bonjour", "Bonjour à tous !", "BONJOUR 😊", "  bonjour !", "👋 Bonjour", "**Bonjour**",
                     "Bonsoir tout le monde", "SALUT !", "Coucou", "Hey !", "hello", "Hi everyone", "yo",
                     "ola", "Olá !", "Olà", "Hola amigos", "Holà !", "👋 **Bonsoir**", "  hEy les amis",
                     "Ola\u0301 !"):
            with self.subTest(text=text):
                self.assertTrue(is_greeting(text), text)
        for text in ("", "bonne journée", "bonjournee", "Je lui ai dit bonjour", "`bonjour`", "> bonjour",
                     "https://bonjour.fr", "bonsoiree", "salutation", "heyday", "helloworld", "holala",
                     "olaf", "high", "yoga", "On se dit bonsoir", "`hello`", "> salut"):
            with self.subTest(text=text):
                self.assertFalse(is_greeting(text), text)

    def test_greeting_config_is_optional_and_validated(self):
        raw = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
        raw.pop("greetings")
        path = Path(self.tmp.name) / "config.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        self.assertTrue(load_config(path, preview=True).greetings.enabled)
        for invalid in ({"enabled": "false"}, {"channel_ids": "123"}, {"channel_ids": [True]}):
            raw["greetings"] = invalid
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_config(path, preview=True)
        raw["greetings"] = {"enabled": False, "channel_ids": ["456"]}
        path.write_text(json.dumps(raw), encoding="utf-8")
        self.assertEqual(load_config(path, preview=True).greetings, GreetingsConfig(False, (456,)))

    def test_daily_greeting_reservation_survives_database_reopen(self):
        day = date(2026, 10, 19)
        self.assertTrue(self.state.claim_greeting(123, day, 88))
        other = State(self.config.state_db)
        try:
            self.assertFalse(other.claim_greeting(123, day, 88))
            self.assertTrue(other.claim_greeting(123, day + timedelta(days=1), 88))
            self.assertTrue(other.claim_greeting(123, day, 89))
        finally:
            other.close()

    def test_daypart_boundaries_in_paris_even_with_utc_input(self):
        for hour, minute, expected in ((4, 59, "evening"), (5, 0, "morning"),
                                       (11, 59, "morning"), (12, 0, "noon"),
                                       (13, 59, "noon"), (14, 0, "afternoon"),
                                       (17, 59, "afternoon"), (18, 0, "evening"),
                                       (23, 59, "evening"), (0, 0, "evening")):
            for month in (1, 7, 10):
                local = datetime(2026, month, 25, hour, minute, tzinfo=self.config.timezone)
                with self.subTest(local=local):
                    self.assertEqual(daypart(local.astimezone(timezone.utc)), expected)

    def test_direct_mentions_only_target_the_bot(self):
        for content in ("<@42>", "Bonjour <@!42> !", "Coucou <@42> <@42>"):
            self.assertTrue(is_direct_mention(content, 42))
        for content in ("@everyone", "@here", "@Bot du jour", "<@142>", "<@&42>", "", "<@43>"):
            self.assertFalse(is_direct_mention(content, 42))

    def test_mention_config_defaults_and_validation(self):
        raw = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
        raw.pop("mentions")
        path = Path(self.tmp.name) / "config.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        self.assertEqual(load_config(path, preview=True).mentions, MentionsConfig())
        for invalid in (None, [], {"enabled": 1}, {"channel_ids": "456"},
                        {"channel_ids": [True]}, {"channel_ids": ["oops"]},
                        {"cooldown_seconds": True}, {"cooldown_seconds": 0},
                        {"cooldown_seconds": 3601}, {"cooldown_seconds": 1.5}):
            with self.subTest(invalid=invalid):
                raw["mentions"] = invalid
                path.write_text(json.dumps(raw), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_config(path, preview=True)
        raw["mentions"] = {"enabled": False, "channel_ids": ["456"], "cooldown_seconds": 60}
        path.write_text(json.dumps(raw), encoding="utf-8")
        self.assertEqual(load_config(path, preview=True).mentions, MentionsConfig(False, (456,), 60))

    def test_mention_cooldown_survives_restart_and_clock_change(self):
        now = datetime(2026, 10, 25, 0, 59, 50, tzinfo=timezone.utc)
        self.assertTrue(self.state.claim_mention(123, 88, now, 30))
        other = State(self.config.state_db)
        try:
            self.assertFalse(other.claim_mention(123, 88, (now + timedelta(seconds=29)).astimezone(self.config.timezone), 30))
            self.assertTrue(other.claim_mention(123, 88, (now + timedelta(seconds=30)).astimezone(self.config.timezone), 30))
            self.assertTrue(other.claim_mention(123, 89, now, 30))
        finally:
            other.close()


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

    async def test_recover_new_bulletin_without_technical_footer(self):
        self.state.plan(self.config, self.day)
        self.state.set_status(123, self.day, "sending")
        self.channel.messages = [SimpleNamespace(id=78, author=SimpleNamespace(id=42),
                                                content=render(self.config, self.day, ["René"]),
                                                created_at=self.now)]
        await self.client.tick(self.now)
        self.channel.send.assert_not_awaited()
        self.assertEqual(self.state.plan(self.config, self.day)["message_id"], "78")

    async def test_bulletin_detection_ignores_greetings_other_authors_and_dates(self):
        text = render(self.config, self.day, ["René"])
        self.channel.messages = [
            SimpleNamespace(author=SimpleNamespace(id=42), content="Bonjour **René** !", created_at=self.now),
            SimpleNamespace(author=SimpleNamespace(id=99), content=text, created_at=self.now),
            SimpleNamespace(author=SimpleNamespace(id=42), content=text, created_at=self.now - timedelta(days=1)),
            SimpleNamespace(author=SimpleNamespace(id=42), created_at=self.now,
                            content=render(self.config, self.day - timedelta(days=1), ["Luc"])),
        ]
        self.assertIsNone(await find_bulletin(self.channel, 42, self.day, self.config.timezone))

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

    def greeting_message(self, user_id=88, display_name="Pseudo du serveur", content="Bonjour à tous !"):
        return SimpleNamespace(guild=SimpleNamespace(id=123), channel=SimpleNamespace(id=456),
                               author=SimpleNamespace(id=user_id, bot=False, display_name=display_name),
                               id=1000 + user_id, created_at=self.now,
                               webhook_id=None, content=content, reply=AsyncMock())

    async def test_greet_once_across_channels_and_nickname_changes(self):
        first = self.greeting_message(content="Bonsoir à tous !")
        await self.client.on_message(first)
        again = self.greeting_message(display_name="Nouveau pseudo", content="Hey !")
        again.channel.id = 789
        await self.client.on_message(again)
        first.reply.assert_awaited_once()
        self.assertIn("Pseudo du serveur", first.reply.call_args.args[0])
        again.reply.assert_not_awaited()

    async def test_reply_to_alternative_greetings(self):
        for user_id, content in enumerate(("Bonsoir !", "Hey !", "Ola !", "Hello !", "Salut !", "Coucou !"), start=90):
            with self.subTest(content=content):
                message = self.greeting_message(user_id=user_id, content=content)
                await self.client.on_message(message)
                message.reply.assert_awaited_once()

    async def test_distinct_members_with_same_nickname_are_greeted(self):
        first, second = self.greeting_message(88), self.greeting_message(89)
        await self.client.on_message(first)
        await self.client.on_message(second)
        first.reply.assert_awaited_once()
        second.reply.assert_awaited_once()

    async def test_greeting_day_changes_at_paris_midnight_not_utc(self):
        message = self.greeting_message()
        self.now = datetime(2026, 10, 19, 21, 59, tzinfo=timezone.utc)
        await self.client.on_message(message)
        self.now = datetime(2026, 10, 19, 22, 1, tzinfo=timezone.utc)
        await self.client.on_message(message)
        self.assertEqual(message.reply.await_count, 2)

    async def test_clock_change_does_not_allow_second_greeting(self):
        message = self.greeting_message()
        self.now = datetime(2026, 10, 25, 0, 59, tzinfo=timezone.utc)
        await self.client.on_message(message)
        self.now = datetime(2026, 10, 25, 1, 1, tzinfo=timezone.utc)
        await self.client.on_message(message)
        message.reply.assert_awaited_once()

    async def test_concurrent_greetings_send_only_once(self):
        message = self.greeting_message()
        await asyncio.gather(self.client.on_message(message), self.client.on_message(message))
        message.reply.assert_awaited_once()

    async def test_greetings_ignore_bots_webhooks_dms_and_other_guilds(self):
        messages = [self.greeting_message(user_id=90 + i) for i in range(5)]
        messages[0].author.bot = True
        messages[1].webhook_id = 12
        messages[2].guild = None
        messages[3].guild.id = 999
        messages[4].content = "J'ai déjà dit bonjour"
        for message in messages:
            await self.client.on_message(message)
            message.reply.assert_not_awaited()

    async def test_greeting_channel_allowlist_and_disable(self):
        self.client.config = replace(self.config, greetings=GreetingsConfig(True, (789,)))
        message = self.greeting_message()
        await self.client.on_message(message)
        message.reply.assert_not_awaited()
        self.client.config = replace(self.config, greetings=GreetingsConfig(False))
        await self.client.on_message(message)
        message.reply.assert_not_awaited()

    async def test_greeting_mentions_are_disabled(self):
        message = self.greeting_message(display_name="@everyone **Chef**")
        await self.client.on_message(message)
        self.assertIn("@\u200beveryone", message.reply.call_args.args[0])
        self.assertIn(r"\*\*Chef\*\*", message.reply.call_args.args[0])
        kwargs = message.reply.call_args.kwargs
        self.assertFalse(kwargs["mention_author"])
        self.assertFalse(kwargs["allowed_mentions"].everyone)
        self.assertFalse(kwargs["allowed_mentions"].users)

    async def test_failed_greeting_is_not_blindly_repeated(self):
        message = self.greeting_message()
        message.reply.side_effect = TimeoutError("réponse perdue")
        with self.assertLogs("botdujour", level="ERROR"):
            await self.client.on_message(message)
        await self.client.on_message(message)
        message.reply.assert_awaited_once()

    async def test_explicitly_refused_greeting_can_retry_after_permission_fix(self):
        message = self.greeting_message()
        message.reply.side_effect = discord.Forbidden(SimpleNamespace(status=403, reason="Forbidden"), "Missing permissions")
        with self.assertLogs("botdujour", level="WARNING"):
            await self.client.on_message(message)
        message.reply.side_effect = None
        await self.client.on_message(message)
        self.assertEqual(message.reply.await_count, 2)

    async def test_disabled_greetings_do_not_request_privileged_intent(self):
        config = replace(self.config, greetings=GreetingsConfig(False))
        client = BulletinClient(config, self.state, self.session)
        try:
            self.assertFalse(client.intents.message_content)
            self.assertTrue(client.intents.guild_messages)  # L'inactivité reçoit aussi les messages.
        finally:
            await client.close()

    async def test_greetings_use_the_current_paris_daypart(self):
        for hour, expected in ((8, "Bonjour"), (12, "Bon appétit"),
                               (15, "après-midi"), (20, "Bonsoir")):
            self.now = self.now.replace(hour=hour)
            message = self.greeting_message(user_id=100 + hour)
            with patch("bonjour.greetings.secrets.choice", side_effect=lambda choices: choices[0]):
                await self.client.on_message(message)
            self.assertIn(expected, message.reply.call_args.args[0])

    async def test_ping_is_independent_from_daily_greeting_and_does_not_ping_back(self):
        await self.client.on_message(self.greeting_message())
        message = self.greeting_message(content="<@42> coucou !", display_name="@everyone **Chef**")
        await self.client.on_message(message)
        message.reply.assert_awaited_once()
        self.assertIn("@\u200beveryone", message.reply.call_args.args[0])
        self.assertIn(r"\*\*Chef\*\*", message.reply.call_args.args[0])
        kwargs = message.reply.call_args.kwargs
        self.assertFalse(kwargs["mention_author"])
        self.assertFalse(kwargs["allowed_mentions"].users or kwargs["allowed_mentions"].roles
                         or kwargs["allowed_mentions"].everyone)

    async def test_ping_and_greeting_only_produce_one_reply_without_using_daily_greeting(self):
        message = self.greeting_message(content="Bonjour <@42> <@!42> !")
        await self.client.on_message(message)
        message.reply.assert_awaited_once()
        greeting = self.greeting_message()
        await self.client.on_message(greeting)
        greeting.reply.assert_awaited_once()

    async def test_concurrent_pings_and_cross_channel_cooldown(self):
        message = self.greeting_message(content="<@42>")
        await asyncio.gather(self.client.on_message(message), self.client.on_message(message))
        message.reply.assert_awaited_once()
        again = self.greeting_message(content="<@!42>")
        again.channel.id = 789
        self.now += timedelta(seconds=29)
        await self.client.on_message(again)
        again.reply.assert_not_awaited()
        self.now += timedelta(seconds=1)
        await self.client.on_message(again)
        again.reply.assert_awaited_once()
        other = self.greeting_message(user_id=89, content="<@42>")
        await self.client.on_message(other)
        other.reply.assert_awaited_once()

    async def test_pings_ignore_bots_webhooks_dms_other_guilds_and_implicit_mentions(self):
        messages = [self.greeting_message(user_id=90 + i, content="<@42>") for i in range(6)]
        messages[0].author.bot = True
        messages[1].webhook_id = 12
        messages[2].guild = None
        messages[3].guild.id = 999
        messages[4].content = "@everyone <@43>"
        messages[5].content = "Une réponse sans ping explicite"
        messages[5].mentions = [SimpleNamespace(id=42)]
        for message in messages:
            await self.client.on_message(message)
            message.reply.assert_not_awaited()

    async def test_ping_settings_are_independent_from_greetings(self):
        self.client.config = replace(self.config, greetings=GreetingsConfig(False),
                                     mentions=MentionsConfig(True, (789,)))
        blocked = self.greeting_message(content="<@42>")
        await self.client.on_message(blocked)
        blocked.reply.assert_not_awaited()
        allowed = self.greeting_message(content="<@42>")
        allowed.channel.id = 789
        await self.client.on_message(allowed)
        allowed.reply.assert_awaited_once()
        self.client.config = replace(self.client.config, mentions=MentionsConfig(False))
        disabled = self.greeting_message(user_id=89, content="<@42>")
        disabled.channel.id = 789
        await self.client.on_message(disabled)
        disabled.reply.assert_not_awaited()

    async def test_mention_only_mode_receives_messages_without_privileged_intent(self):
        config = replace(self.config, greetings=GreetingsConfig(False), inactivity=InactivityConfig(False))
        client = BulletinClient(config, self.state, self.session)
        try:
            self.assertTrue(client.intents.guild_messages)
            self.assertFalse(client.intents.message_content)
        finally:
            await client.close()

    async def test_failed_ping_waits_for_cooldown(self):
        message = self.greeting_message(content="<@42>")
        message.reply.side_effect = TimeoutError("réponse perdue")
        with self.assertLogs("botdujour", level="ERROR"):
            await self.client.on_message(message)
        await self.client.on_message(message)
        message.reply.assert_awaited_once()

    async def test_explicitly_refused_ping_can_retry(self):
        message = self.greeting_message(content="<@42>")
        message.reply.side_effect = discord.Forbidden(SimpleNamespace(status=403, reason="Forbidden"), "Missing permissions")
        with self.assertLogs("botdujour", level="WARNING"):
            await self.client.on_message(message)
        message.reply.side_effect = None
        await self.client.on_message(message)
        self.assertEqual(message.reply.await_count, 2)


if __name__ == "__main__":
    unittest.main()
