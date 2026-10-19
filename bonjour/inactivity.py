"""Relances d'un salon silencieux, textes locaux et sans mention."""
from datetime import datetime, timedelta, timezone
import secrets

from .config import Config

LIGHT = (
    "C'est calme ici… Quelqu'un a activé le mode bibliothèque sans me prévenir ? 📚🤫",
    "Petit contrôle technique : vos claviers sont toujours branchés ? Le mien attend une conversation. ⌨️😄",
    "Le café est prêt, les circuits aussi. Quelqu'un a une bonne nouvelle à partager ? ☕🤖",
    "J'ai rangé tous les octets du salon par ordre alphabétique. Vous faites quoi de beau ? 😄",
    "Le silence est d'or… mais je n'ai toujours pas trouvé où le revendre. Quelqu'un discute ? 🪙😄",
    "Quelqu'un code un truc sympa, ou on regarde tous la barre de chargement avancer ? 💻😄",
    "J'ai demandé une augmentation pour surveiller le silence. On m'a proposé plus de RAM. 🤖",
    "Petite pause dans le silence : racontez-moi votre victoire du jour, même si c'est juste un café réussi ! ☕✨",
)
DARK = (
    "C'est tellement calme ici que même les fantômes ont demandé du télétravail. 👻",
    "J'ai appelé un médium pour relancer le salon. Il attend lui aussi une réponse. 🔮💀",
    "Ambiance cimetière… Au moins, personne ne se plaint du voisinage. 🪦😄",
    "Le salon est si silencieux que mon antivirus l'a classé dans les dossiers défunts. 💀💻",
    "J'ai demandé au silence un signe de vie. Il m'a laissé en vu. 👻",
    "Même le fossoyeur trouve que ce salon manque un peu d'animation. 🪦🤖",
    "Je voulais ressusciter la conversation, mais la notice de nécromancie est en maintenance. 📖💀",
    "Le silence vient de me proposer un CDI. J'hésite : l'ambiance est un peu mortelle. 👻😄",
)

ASCII = (
    "Petit visiteur du salon :\n```text\n /\\_/\\\n( o.o )\n > ^ <\n```\nIl attend une conversation… ou des croquettes. 🐱",
    "Mon collègue du service animation est arrivé :\n```text\n [o_o]\n /|_|\\\n  / \\\n```\nIl est payé en piles et en bonnes blagues. 🤖",
    "Un hibou de garde pour surveiller le silence :\n```text\n  ,_,\n (O,O)\n (   )\n  \" \"\n```\nIl trouve lui aussi que ça manque de bavardages. 🦉",
    "Le salon a reçu un visiteur très occupé :\n```text\n  __\n (oo)\n /||\\\n```\nQuatre bras, et toujours personne pour lancer la discussion. 😄",
)


def binary_message(plain: str) -> str:
    encoded = " ".join(f"{byte:08b}" for byte in plain.encode("ascii"))
    return f"🤖 À décrypter — binaire ASCII, 8 bits par caractère :\n```text\n{encoded}\n```\nIndice : mon humour n'a que deux états, 0 et 1. 😄"


BINARY = tuple(binary_message(text) for text in (
    "Le cafe est pret", "Bonjour les humains", "Quelqu'un est la ?", "Le silence fait des bugs",
))


def choose_prompt(tone: str, previous: str | None = None) -> str:
    jokes = {"light": LIGHT, "dark": DARK, "mixed": LIGHT + DARK}[tone]
    choices = [text for text in jokes + ASCII + BINARY if text != previous]
    return secrets.choice(choices)


def is_due(config: Config, row, now: datetime) -> bool:
    local = now.astimezone(config.timezone)
    if not config.inactivity.enabled or not config.inactivity.start <= local.time() < config.inactivity.end:
        return False
    anchor = datetime.fromisoformat(row["last_human_at"])
    if row["last_prompt_at"]:
        anchor = max(anchor, datetime.fromisoformat(row["last_prompt_at"]))
    elapsed = now.astimezone(timezone.utc) - anchor
    return elapsed >= timedelta(minutes=config.inactivity.after_minutes)
