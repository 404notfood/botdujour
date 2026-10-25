"""Lancement : python bot.py ; aperçu local : python bot.py --preview --offline."""
import argparse
import asyncio
from datetime import date, datetime, time
import logging
import os
from pathlib import Path

import aiohttp
import discord
from discord import app_commands
from dotenv import load_dotenv

from bonjour.config import Config, load_config
from bonjour.content import date_line, marker, render
from bonjour.greetings import is_greeting, make_reply
from bonjour.goodnight import make_goodnight
from bonjour.inactivity import choose_prompt, is_due
from bonjour.mentions import is_direct_mention, make_mention_reply
from bonjour.namedays import get_names
from bonjour.state import State, single_instance
from bonjour.voice import append_voice_invitation, voice_arrival

log = logging.getLogger("botdujour")


async def find_bulletin(channel, author_id: int, day: date, zone):
    midnight = datetime.combine(day, time.min, zone)
    async for message in channel.history(limit=None, after=midnight, oldest_first=False):
        if (message.author.id == author_id and message.created_at.astimezone(zone).date() == day
                and any(line == date_line(day) or line.startswith(f"-# {marker(day)}")
                        for line in message.content.splitlines())):
            return message
    return None


class BulletinClient(discord.Client):
    def __init__(self, config: Config, state: State, session: aiohttp.ClientSession):
        intents = discord.Intents.none()
        intents.guilds = True
        intents.guild_messages = config.greetings.enabled or config.inactivity.enabled or config.mentions.enabled
        intents.message_content = config.greetings.enabled
        intents.voice_states = config.voice.announce_joins or (config.inactivity.enabled and config.inactivity.include_voice)
        super().__init__(intents=intents, allowed_mentions=discord.AllowedMentions.none())
        self.config, self.state, self.session = config, state, session
        self.tree = app_commands.CommandTree(self)
        self.worker = None
        self.logged_day = None
        self.activity_needs_sync = True
        guild = discord.Object(id=config.guild_id)

        @self.tree.command(name="bonjour-apercu", description="Prévisualiser le bulletin, visible uniquement par vous.", guild=guild)
        @app_commands.guild_only()
        @app_commands.default_permissions(manage_guild=True)
        @app_commands.checks.has_permissions(manage_guild=True)
        async def preview(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            today = datetime.now(config.timezone).date()
            names = await get_names(session, state, today)
            await interaction.followup.send(render(config, today, names), ephemeral=True,
                                            allowed_mentions=discord.AllowedMentions.none())

        @self.tree.error
        async def command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
            if isinstance(error, app_commands.MissingPermissions):
                message = "La permission Gérer le serveur est nécessaire pour cet aperçu."
            else:
                log.error("Échec de l'aperçu : %s", type(error).__name__)
                message = "L'aperçu a échoué. Consulter les journaux du bot."
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)

    async def setup_hook(self):
        await self.tree.sync(guild=discord.Object(id=self.config.guild_id))
        self.worker = asyncio.create_task(self.scheduler(), name="bulletin-quotidien")

    async def on_ready(self):
        self.activity_needs_sync = True
        log.info("Connecté comme %s ; serveur %s, salon %s.", self.user, self.config.guild_id, self.config.channel_id)
        try:
            await self.destination(self.config.channel_id)
            log.info("Serveur, salon et permissions vérifiés.")
        except (ValueError, discord.HTTPException):
            log.exception("Vérifier les identifiants et les permissions du salon configuré.")

    async def on_message(self, message: discord.Message):
        config = self.config
        if (config.inactivity.enabled and message.guild is not None
                and message.guild.id == config.guild_id and message.channel.id == config.channel_id):
            self.state.observe_activity(config.guild_id, config.channel_id, message.id, message.created_at,
                                        human=not message.author.bot and message.webhook_id is None)
        if (message.guild is None
                or message.guild.id != config.guild_id or message.author.bot
                or message.webhook_id is not None):
            return
        now = datetime.now(config.timezone)
        if (config.mentions.enabled and self.user is not None
                and is_direct_mention(message.content, self.user.id)
                and (not config.mentions.channel_ids or message.channel.id in config.mentions.channel_ids)):
            # Une seule réponse si un message contient à la fois « bonjour » et un ping.
            await self.reply_to_mention(message, now)
            return
        if not config.greetings.enabled:
            return
        if config.greetings.channel_ids and message.channel.id not in config.greetings.channel_ids:
            return
        if not is_greeting(message.content):
            return
        today = now.date()
        # Réservation persistante avant le premier await pour éviter deux réponses simultanées.
        if not self.state.claim_greeting(config.guild_id, today, message.author.id):
            return
        try:
            await message.reply(make_reply(message.author.display_name, now), mention_author=False,
                                allowed_mentions=discord.AllowedMentions.none())
        except (discord.Forbidden, discord.NotFound):
            self.state.release_greeting(config.guild_id, today, message.author.id)
            log.warning("Réponse bonjour refusée dans le salon %s : vérifier les permissions ou le message source.",
                        message.channel.id)
        except Exception:
            # Réponse réseau incertaine : ne pas risquer de resaluer ce membre aujourd'hui.
            log.exception("Réponse bonjour incertaine dans le salon %s ; aucun nouvel essai pour ce membre aujourd'hui.",
                          message.channel.id)

    async def reply_to_mention(self, message: discord.Message, now: datetime):
        config = self.config
        if not self.state.claim_mention(config.guild_id, message.author.id, now, config.mentions.cooldown_seconds):
            return
        try:
            await message.reply(make_mention_reply(message.author.display_name), mention_author=False,
                                allowed_mentions=discord.AllowedMentions.none())
        except (discord.Forbidden, discord.NotFound):
            self.state.release_mention(config.guild_id, message.author.id, now)
            log.warning("Réponse au ping refusée dans le salon %s : vérifier les permissions ou le message source.",
                        message.channel.id)
        except Exception:
            log.exception("Réponse au ping incertaine dans le salon %s ; délai conservé avant une nouvelle réponse.",
                          message.channel.id)

    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState,
                                    after: discord.VoiceState):
        config = self.config
        if (not config.voice.announce_joins or member.bot or member.guild.id != config.guild_id
                or after.channel is None or before.channel == after.channel):
            return
        message = voice_arrival(member, after.channel)
        if message is None:
            return
        try:
            channel = await self.destination(config.channel_id)
            await channel.send(message, allowed_mentions=discord.AllowedMentions.none())
        except (ValueError, discord.Forbidden, discord.NotFound):
            log.warning("Annonce d'arrivée en vocal refusée : vérifier le salon textuel et ses permissions.")
        except Exception:
            # Ne pas réessayer une annonce dont l'envoi peut déjà avoir abouti.
            log.exception("Échec de l'annonce d'arrivée en vocal ; aucun renvoi automatique.")

    async def close(self):
        if self.worker:
            self.worker.cancel()
            try:
                await self.worker
            except asyncio.CancelledError:
                pass
        await super().close()

    async def destination(self, channel_id: int):
        channel = self.get_channel(channel_id) or await self.fetch_channel(channel_id)
        if not isinstance(channel, discord.TextChannel) or channel.guild.id != self.config.guild_id:
            raise ValueError("Le salon doit être un salon textuel du serveur configuré.")
        member = channel.guild.me
        if member is None:
            raise ValueError("Le bot n'est pas membre du serveur configuré.")
        permissions = channel.permissions_for(member)
        if not (permissions.view_channel and permissions.send_messages and permissions.read_message_history):
            raise ValueError("Permissions requises dans le salon : Voir le salon, Envoyer des messages et Voir les anciens messages.")
        return channel

    async def tick(self, now: datetime):
        config = self.config
        now = now.astimezone(config.timezone)
        day = now.date()
        plan = self.state.plan(config, day)
        if day != self.logged_day:
            log.info("Bulletin du %s prévu à %s (heure de Paris), état : %s.",
                     day, datetime.fromisoformat(plan["target"]).strftime("%H:%M:%S"), plan["status"])
            self.logged_day = day
        if plan["status"] in ("sent", "skipped", "uncertain"):
            return
        if plan["status"] == "pending":
            if now >= datetime.combine(day, config.end, config.timezone):
                self.state.set_status(config.guild_id, day, "skipped")
                log.warning("Fenêtre du matin dépassée : bulletin du %s ignoré.", day)
                return
            if now < datetime.fromisoformat(plan["target"]):
                return
        channel = await self.destination(int(plan["channel"]))
        # Réconcilier l'historique avant tout envoi, notamment après un arrêt brutal.
        existing = await find_bulletin(channel, self.user.id, day, config.timezone)
        if existing:
            self.state.set_status(config.guild_id, day, "sent", existing.id)
            log.info("Bulletin du %s déjà présent, aucun nouvel envoi.", day)
            return
        if plan["status"] == "sending":
            self.state.set_status(config.guild_id, day, "uncertain")
            log.error("Envoi du %s interrompu sans accusé de réception. Aucun renvoi automatique ; vérifier le salon.", day)
            return
        names = await get_names(self.session, self.state, day)
        message = render(config, day, names)
        # Le réseau peut prendre du temps : ne pas envoyer après 09:00.
        if datetime.now(config.timezone) >= datetime.combine(day, config.end, config.timezone):
            self.state.set_status(config.guild_id, day, "skipped")
            return
        self.state.set_status(config.guild_id, day, "sending")
        try:
            sent = await channel.send(message, allowed_mentions=discord.AllowedMentions.none())
        except (discord.Forbidden, discord.NotFound):
            # Refus explicite : Discord n'a pas créé de message, une reprise reste sûre.
            self.state.set_status(config.guild_id, day, "pending")
            raise
        except Exception:
            # Conserver 'sending'. Au prochain passage, rechercher le message.
            log.exception("Réponse d'envoi incertaine pour le %s, contrôle de l'historique au prochain passage.", day)
            return
        self.state.set_status(config.guild_id, day, "sent", sent.id)
        log.info("Bulletin publié : %s", sent.id)

    async def scheduler(self):
        await self.wait_until_ready()
        while not self.is_closed():
            if self.is_ready():
                try:
                    await self.tick(datetime.now(self.config.timezone))
                except Exception:
                    log.exception("Échec du passage du planificateur ; nouvel essai dans 30 secondes.")
                try:
                    await self.inactivity_tick(datetime.now(self.config.timezone))
                except Exception:
                    log.exception("Échec de la vérification d'inactivité ; nouvel essai dans 30 secondes.")
                try:
                    await self.goodnight_tick(datetime.now(self.config.timezone))
                except Exception:
                    log.exception("Échec de la vérification du message de bonne nuit ; nouvel essai dans 30 secondes.")
            await asyncio.sleep(30)

    async def goodnight_tick(self, now: datetime):
        config = self.config
        now = now.astimezone(config.timezone)
        day = now.date()
        if (not config.goodnight.enabled or now.time() < config.goodnight.at
                or self.state.has_goodnight(config.guild_id, day)):
            return
        channel = await self.destination(config.channel_id)
        # Ne pas publier le message de la veille si le réseau a passé minuit.
        current = datetime.now(config.timezone)
        if current.date() != day or current.time() < config.goodnight.at:
            return
        text = make_goodnight()
        # Réserver avant l'envoi : pas de doublon après redémarrage ou appel simultané.
        if not self.state.claim_goodnight(config.guild_id, day):
            return
        try:
            await channel.send(text, allowed_mentions=discord.AllowedMentions.none())
        except (discord.Forbidden, discord.NotFound):
            self.state.release_goodnight(config.guild_id, day)
            log.warning("Message de bonne nuit refusé : vérifier le salon et ses permissions.")
        except Exception:
            log.exception("Envoi de bonne nuit incertain ; aucun renvoi automatique pour le %s.", day)
        else:
            log.info("Message de bonne nuit publié pour le %s.", day)

    async def inactivity_tick(self, now: datetime):
        config = self.config
        if not config.inactivity.enabled:
            return
        row = self.state.activity(config.guild_id, config.channel_id, now)
        if not self.activity_needs_sync and not is_due(config, row, now):
            return
        channel = await self.destination(config.channel_id)
        # Retrouver aussi l'activité pendant une déconnexion. Ne lire aucun contenu.
        async for message in channel.history(limit=None, after=datetime.fromisoformat(row["last_message_at"]), oldest_first=True):
            self.state.observe_activity(config.guild_id, config.channel_id, message.id, message.created_at,
                                        human=not message.author.bot and message.webhook_id is None)
        self.activity_needs_sync = False
        now = datetime.now(config.timezone)
        row = self.state.activity(config.guild_id, config.channel_id, now)
        if not is_due(config, row, now):
            return
        text = choose_prompt(config.inactivity.tone, row["last_prompt_text"], now)
        message = (append_voice_invitation(text, self.get_guild(config.guild_id))
                   if config.inactivity.include_voice else text)
        # Conserver uniquement la blague pour éviter sa répétition malgré les changements en vocal.
        if not self.state.claim_inactivity(config.guild_id, config.channel_id, row, now, text):
            return
        try:
            sent = await channel.send(message, allowed_mentions=discord.AllowedMentions.none())
        except (discord.Forbidden, discord.NotFound):
            self.state.release_inactivity(config.guild_id, config.channel_id, now, row)
            log.warning("Relance refusée dans le salon %s : vérifier les permissions.", config.channel_id)
        except Exception:
            log.exception("Réponse réseau incertaine pour la relance du salon %s ; attendre le prochain délai complet avant un nouvel essai.", config.channel_id)
        else:
            # Mettre à jour avant même que notre événement on_message ne revienne.
            self.state.observe_activity(config.guild_id, config.channel_id, sent.id, sent.created_at, human=False)
            self.state.complete_inactivity(config.guild_id, config.channel_id, now, sent.created_at)
            log.info("Relance d'inactivité publiée dans le salon %s.", config.channel_id)


async def run(args, config: Config):
    if args.preview and args.offline:
        print(render(config, args.date or datetime.now(config.timezone).date(), None))
        return
    token = os.environ.get("DISCORD_TOKEN", "").strip()
    if not args.preview and (not token or token == "votre_token_discord"):
        raise ValueError("Renseigner DISCORD_TOKEN dans .env avant de démarrer le bot.")
    with single_instance(config.state_db):
        state = State(config.state_db)
        try:
            async with aiohttp.ClientSession(headers={"User-Agent": "BotDuJour/1.0"}) as session:
                if args.preview:
                    day = args.date or datetime.now(config.timezone).date()
                    print(render(config, day, await get_names(session, state, day)))
                else:
                    async with BulletinClient(config, state, session) as client:
                        await client.start(token)
        finally:
            state.close()


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s : %(message)s")
    parser = argparse.ArgumentParser(description="Bot Discord du bonjour quotidien (heure de Paris).")
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parent / "config.json")
    parser.add_argument("--check", action="store_true", help="Vérifier les fichiers sans se connecter à Discord.")
    parser.add_argument("--preview", action="store_true", help="Afficher le bulletin sans le publier.")
    parser.add_argument("--offline", action="store_true", help="Aperçu sans appel à Nominis (avec --preview).")
    parser.add_argument("--date", type=date.fromisoformat, help="Date de l'aperçu : AAAA-MM-JJ.")
    args = parser.parse_args()
    if (args.offline or args.date) and not args.preview:
        parser.error("--offline et --date nécessitent --preview.")
    load_dotenv(Path(__file__).resolve().parent / ".env", override=False)
    try:
        config = load_config(args.config, preview=args.preview)
        if args.check:
            # Vérifie aussi la structure du calendrier et la taille du bulletin du jour.
            render(config, datetime.now(config.timezone).date(), None)
            print("Configuration valide. Les identifiants et permissions Discord seront vérifiés à la connexion.")
        elif args.preview and args.offline:
            print(render(config, args.date or datetime.now(config.timezone).date(), None))
        else:
            asyncio.run(run(args, config))
    except discord.PrivilegedIntentsRequired:
        parser.exit(1, "Erreur : activer Message Content Intent dans le portail Discord, rubrique Bot → Privileged Gateway Intents, ou désactiver greetings.enabled dans config.json.\n")
    except (ValueError, RuntimeError, OSError, discord.LoginFailure, discord.HTTPException) as exc:
        parser.exit(1, f"Erreur : {exc}\n")
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
