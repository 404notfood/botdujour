"""Invitations vers les vocaux publics occupés, sans notification."""
import discord

from .content import safe


def is_public_voice(channel) -> bool:
    if not isinstance(channel, discord.VoiceChannel):
        return False
    guild = channel.guild
    if guild.me is None or channel == guild.afk_channel:
        return False
    public = channel.permissions_for(guild.default_role)
    if not (public.view_channel and public.connect and channel.permissions_for(guild.me).view_channel):
        return False
    # Rester prudent : ne pas annoncer un salon fermé à certains rôles ou membres.
    return not any(overwrite.view_channel is False or overwrite.connect is False
                   for overwrite in channel.overwrites.values())


def member_name(member) -> str:
    # Neutraliser le Markdown, les mentions et les retours à la ligne des pseudos.
    name = safe(" ".join(member.display_name.split())).replace("<", "<\u200b")
    return f"**{name}**"


def member_names(members) -> str:
    members = sorted(members, key=lambda member: (member.display_name.casefold(), member.id))
    names = [member_name(member) for member in members[:5]]
    if len(members) > 5:
        remaining = len(members) - 5
        names.append("1 autre membre" if remaining == 1 else f"{remaining} autres membres")
    return " et ".join(names) if len(names) < 3 else ", ".join(names[:-1]) + " et " + names[-1]


def voice_arrival(member, channel) -> str | None:
    if not is_public_voice(channel):
        return None
    text = f"🎙️ {member_name(member)} vient de rejoindre {channel.mention} !"
    occupants = channel.members
    others = [other for other in occupants if not other.bot and other.id != member.id]
    if others:
        text += f"\nÉgalement en vocal : {member_names(others)}."
    if not channel.user_limit or len(occupants) < channel.user_limit:
        text += "\nVenez discuter avec eux !" if others else "\nVenez lui tenir compagnie !"
    return text


def append_voice_invitation(text: str, guild: discord.Guild | None) -> str:
    if guild is None or guild.me is None:
        return text
    lines = []
    heading = "\n\n🎙️ Vous pouvez aussi venir discuter en vocal !"
    for channel in guild.voice_channels:
        if not is_public_voice(channel):
            continue
        occupants = channel.members
        members = [member for member in occupants if not member.bot]
        if not members or (channel.user_limit and len(occupants) >= channel.user_limit):
            continue
        line = f"• Rejoignez {member_names(members)} dans {channel.mention} !"
        candidate = text + heading + "\n" + "\n".join(lines + [line])
        # Discord compte les unités UTF-16 ; les emojis peuvent en occuper deux.
        if len(candidate.encode("utf-16-le")) // 2 > 2000:
            break
        lines.append(line)
        if len(lines) == 5:
            break
    return text + heading + "\n" + "\n".join(lines) if lines else text
