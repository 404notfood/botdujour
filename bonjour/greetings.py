"""Salutations locales, sans IA et sans conservation du contenu des messages."""
import re
import secrets
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

from .content import safe
from .dayparts import daypart


GREETING = re.compile(
    r"^\s*(?:👋\ufe0f?\s*)?[*_]*(?:bonjour|bonsoir|salut|coucou|hey|hello|hi|yo|ol[aàá]|hol[aà])\b",
    re.IGNORECASE,
)
REPLIES = {
    "morning": (
        "Bonjour **{name}** ! Bien dormi ? J'ai demandé au café de te réveiller doucement. Il a sorti un mégaphone. ☕📣",
        "Salut **{name}** ! Comment ça va ce matin ? Mon grille-pain annonce une journée croustillante, mais il manque d'objectivité. 🍞😄",
        "Bonjour **{name}** ! Prêt pour la matinée ? Mes neurones sont en réunion avec une tartine. Ça négocie la confiture. 🧠🍓",
        "Salut **{name}** ! Bien réveillé ? J'ai mis le soleil en mode turbo et mes circuits en mode croissant. 🥐☀️",
    ),
    "noon": (
        "Salut **{name}** ! Bon appétit pour ce midi ! Mon estomac vient de lancer une pétition pour devenir une raclette. 🧀😄",
        "Coucou **{name}** ! Comment se passe ta pause de midi ? J'ai commandé une salade, elle est arrivée avec un avocat. Le procès commence. 🥑⚖️",
        "Salut **{name}** ! C'est l'heure du déjeuner : même mes bugs sont partis à la cantine. Profite de ta pause ! 🍽️🤖",
        "Hello **{name}** ! Bon appétit ! J'ai essayé de compiler des pâtes ce midi. Résultat : al dente.exe a cessé de fonctionner. 🍝💻",
    ),
    "afternoon": (
        "Salut **{name}** ! Comment va cet après-midi ? Mon cerveau charge à 12 %, mais le goûter promet une mise à jour. 🍪🔋",
        "Coucou **{name}** ! Bel après-midi ! J'ai confié ma productivité à un hamster. Il a pris un RTT dans sa roue. 🐹😄",
        "Salut **{name}** ! La journée avance bien ? Cet après-midi, mes circuits carburent au biscuit et à l'optimisme approximatif. 🍪🤖",
        "Hello **{name}** ! Bon après-midi ! Si tu croises ma motivation, dis-lui que sa pause café dure depuis trois heures. ☕🕵️",
    ),
    "evening": (
        "Bonsoir **{name}** ! Comment vas-tu ? Mes circuits ont enfilé leur pyjama et le canapé m'a nommé ministre de la détente. 🛋️👑",
        "Salut **{name}** ! Ambiance du soir : j'ai mis les soucis en sourdine. Ils communiquent maintenant par signaux de fumée. 🌙😄",
        "Bonsoir **{name}** ! Tu passes un bon moment ? Le mode détente est activé, surveillé par un hibou en chaussons. 🦉🥿",
        "Coucou **{name}** ! La lune assure la permanence. Moi, je négocie une couverture avec un pingouin syndiqué. 🌙🐧",
    ),
}


def is_greeting(content: str) -> bool:
    return bool(GREETING.match(unicodedata.normalize("NFC", content)))


def make_reply(display_name: str, now: datetime | None = None) -> str:
    now = now or datetime.now(ZoneInfo("Europe/Paris"))
    return secrets.choice(REPLIES[daypart(now)]).format(name=safe(display_name))
