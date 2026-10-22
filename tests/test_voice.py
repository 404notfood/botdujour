import unittest

import discord

from bonjour.voice import append_voice_invitation


class VoiceInvitationTests(unittest.TestCase):
    def setUp(self):
        intents = discord.Intents(guilds=True, voice_states=True)
        self.client = discord.Client(intents=intents)
        state = self.client._connection
        state.user = discord.ClientUser(state=state, data=self.user(42, "Bot", bot=True))
        self.data = {
            "id": "123", "owner_id": "999", "name": "Serveur", "afk_channel_id": "790",
            "roles": [{"id": "123", "name": "@everyone", "permissions": str(
                discord.Permissions(view_channel=True, connect=True).value)}],
            "channels": [self.channel(789), self.channel(790), self.channel(791)],
            "members": [self.member(42, "Bot", bot=True), self.member(88, "Alex"),
                        self.member(89, "Emma"), self.member(90, "Musique", bot=True)],
            "voice_states": [self.voice(88, 789), self.voice(89, 789), self.voice(90, 789)],
        }

    @staticmethod
    def user(member_id, name, *, bot=False):
        return {"id": str(member_id), "username": name, "discriminator": "0", "avatar": None, "bot": bot}

    @classmethod
    def member(cls, member_id, name, *, bot=False):
        return {"user": cls.user(member_id, name, bot=bot), "nick": name, "roles": [], "flags": 0}

    @staticmethod
    def channel(channel_id, **kwargs):
        return {"id": str(channel_id), "name": "Vocal", "type": 2, "position": channel_id,
                "permission_overwrites": [], "user_limit": 0, "bitrate": 64000, **kwargs}

    @staticmethod
    def voice(member_id, channel_id):
        return {"user_id": str(member_id), "channel_id": str(channel_id), "session_id": "test",
                "deaf": False, "mute": False, "self_deaf": False, "self_mute": False,
                "self_video": False, "suppress": False}

    def render(self, text="Une petite pause ?"):
        guild = discord.Guild(data=self.data, state=self.client._connection)
        return append_voice_invitation(text, guild)

    def test_public_voice_lists_cached_members_without_members_intent(self):
        self.assertFalse(self.client.intents.members)
        message = self.render()
        self.assertIn("Rejoignez **Alex** et **Emma** dans <#789>", message)
        self.assertNotIn("Musique", message)

    def test_multiple_channels_and_current_presence(self):
        self.data["voice_states"][1] = self.voice(89, 791)
        message = self.render()
        self.assertIn("Rejoignez **Alex** dans <#789>", message)
        self.assertIn("Rejoignez **Emma** dans <#791>", message)
        self.data["voice_states"] = [self.voice(89, 791)]
        self.assertNotIn("Alex", self.render())

    def test_empty_bot_only_and_afk_channels_are_ignored(self):
        for states in ([], [self.voice(90, 789)], [self.voice(88, 790)]):
            with self.subTest(states=states):
                self.data["voice_states"] = states
                self.assertEqual(self.render(), "Une petite pause ?")
        self.assertEqual(append_voice_invitation("Pause", None), "Pause")

    def test_restricted_or_hidden_channels_are_not_disclosed(self):
        for target, kind, denied in ((123, 0, "view_channel"), (123, 0, "connect"),
                                     (42, 1, "view_channel"), (88, 1, "connect"),
                                     (777, 0, "view_channel")):
            with self.subTest(target=target, denied=denied):
                self.data["channels"][0]["permission_overwrites"] = [{
                    "id": str(target), "type": kind, "allow": "0",
                    "deny": str(discord.Permissions(**{denied: True}).value),
                }]
                self.assertEqual(self.render(), "Une petite pause ?")

    def test_role_only_access_is_not_advertised(self):
        self.data["roles"][0]["permissions"] = "0"
        self.assertEqual(self.render(), "Une petite pause ?")

    def test_full_voice_channel_is_not_advertised(self):
        self.data["channels"][0]["user_limit"] = 3  # Deux humains et un bot.
        self.assertEqual(self.render(), "Une petite pause ?")

    def test_nicknames_cannot_inject_formatting_or_mentions(self):
        self.data["members"][1]["nick"] = "@everyone **Chef**\n<#123>"
        message = self.render()
        self.assertNotIn("@everyone", message)
        self.assertNotIn("**Chef**", message)
        self.assertNotIn("<#123>", message)
        self.assertIn(r"\*\*Chef\*\*", message)

    def test_large_guild_stays_within_discord_limit(self):
        self.data["channels"] = [self.channel(800 + i) for i in range(10)]
        self.data["members"] = [self.member(42, "Bot", bot=True)]
        self.data["voice_states"] = []
        for channel in range(10):
            for index in range(8):
                member_id = 1000 + channel * 10 + index
                self.data["members"].append(self.member(member_id, "😀*" * 16))
                self.data["voice_states"].append(self.voice(member_id, 800 + channel))
        message = self.render("😀" * 300)
        self.assertIn("3 autres membres", message)
        self.assertGreater(message.count("• Rejoignez"), 0)
        self.assertLessEqual(message.count("• Rejoignez"), 5)
        self.assertLessEqual(len(message.encode("utf-16-le")) // 2, 2000)
        self.assertEqual(self.render("😀" * 990), "😀" * 990)


if __name__ == "__main__":
    unittest.main()
