"""Invitations vers les vocaux publics occupés, sans notification."""
import discord

from .content import safe


def append_voice_invitation(text: str, guild: discord.Guild | None) -> str:
    if guild is None or guild.me is None:
        return text
    lines = []
    heading = "\n\n🎙️ Vous pouvez aussi venir discuter en vocal !"
    for channel in guild.voice_channels:
        if channel == guild.afk_channel:
            continue
        public = channel.permissions_for(guild.default_role)
        if not (public.view_channel and public.connect and channel.permissions_for(guild.me).view_channel):
            continue
        # Rester prudent : ne pas annoncer un salon fermé à certains rôles ou membres.
        if any(overwrite.view_channel is False or overwrite.connect is False
               for overwrite in channel.overwrites.values()):
            continue
        occupants = channel.members
        members = sorted((member for member in occupants if not member.bot),
                         key=lambda member: (member.display_name.casefold(), member.id))
        if not members or (channel.user_limit and len(occupants) >= channel.user_limit):
            continue
        # Neutraliser le Markdown, les mentions et les retours à la ligne des pseudos.
        names = [f"**{safe(' '.join(member.display_name.split())).replace('<', '<\u200b')}**"
                 for member in members[:5]]
        if len(members) > 5:
            remaining = len(members) - 5
            names.append("1 autre membre" if remaining == 1 else f"{remaining} autres membres")
        people = " et ".join(names) if len(names) < 3 else ", ".join(names[:-1]) + " et " + names[-1]
        line = f"• Rejoignez {people} dans {channel.mention} !"
        candidate = text + heading + "\n" + "\n".join(lines + [line])
        # Discord compte les unités UTF-16 ; les emojis peuvent en occuper deux.
        if len(candidate.encode("utf-16-le")) // 2 > 2000:
            break
        lines.append(line)
        if len(lines) == 5:
            break
    return text + heading + "\n" + "\n".join(lines) if lines else text
