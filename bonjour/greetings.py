"""Salutations locales, sans IA et sans conservation du contenu des messages."""
import re
import secrets
import unicodedata

from .content import safe


GREETING = re.compile(
    r"^\s*(?:👋\ufe0f?\s*)?[*_]*(?:bonjour|bonsoir|salut|coucou|hey|hello|hi|yo|ol[aàá]|hol[aà])\b",
    re.IGNORECASE,
)
REPLIES = (
    "Salut **{name}** ! Comment vas-tu ? Ça va coder aujourd'hui, ou le café réclame encore une mise à jour ? ☕😄",
    "Bonjour **{name}** ! Comment ça va ? Je te souhaite une journée avec beaucoup de sourires et très peu de bugs ! 😊",
    "Salut **{name}** ! Tu vas bien ? Prêt pour une belle journée ? Mes circuits ont déjà mis la bonne humeur en route ! 🤖✨",
    "Bonjour **{name}** ! Comment vas-tu ? J'espère que ton énergie est à 100 %… sinon, on démarre en mode économie ! 😄🔋",
    "Salut **{name}** ! Comment ça va aujourd'hui ? Que tes projets avancent et que ton café reste chaud ! ☕💙",
    "Bonjour **{name}** ! Tu vas bien ? Aujourd'hui, objectif bonne humeur : aucune expérience en robotique requise ! 🤖😊",
    "Salut **{name}** ! Comment vas-tu ? Une nouvelle journée commence : j'ai vérifié, le sourire est toujours gratuit ! 😄",
    "Bonjour **{name}** ! Comment ça va ? Prêt à coder, discuter ou simplement profiter d'un petit moment tranquille ? 😊💻",
)


def is_greeting(content: str) -> bool:
    return bool(GREETING.match(unicodedata.normalize("NFC", content)))


def make_reply(display_name: str) -> str:
    return secrets.choice(REPLIES).format(name=safe(display_name))
