"""Répliques absurdes aux mentions directes du bot, sans service externe."""
import re
import secrets

from .content import safe


REPLIES = (
    "**{name}**, tu m'as invoqué pendant que j'apprenais le moonwalk à une courgette. Elle a déjà plus de rythme que mon processeur. 🥒🕺",
    "Oui **{name}** ? Le conseil des canards vient de valider ta demande. Personne ne sait laquelle, mais ils ont tous fait coin. 🦆📋",
    "**{name}**, j'arrive ! J'étais coincé dans un rond-point avec un GPS qui me disait « assume tes choix ». 🧭🚗",
    "Tu m'as appelé **{name}** ? J'ai trois réponses, deux chaussettes et aucune maîtrise de la situation. 🧦🤖",
    "**{name}**, mon avocat est un brocoli. Il te conseille de garder le silence et de cuire douze minutes à la vapeur. 🥦⚖️",
    "À ton service **{name}** ! J'ai lancé une recherche approfondie. Elle est revenue avec un caillou et beaucoup de fierté. 🪨🔎",
    "**{name}**, la prophétie disait qu'un ping viendrait. On avait prévu un dragon, mais le budget a permis un grille-pain. 🐉🍞",
    "Oui **{name}** ? Mon dernier neurone est parti acheter du pain. Il m'envoie des cartes postales depuis une boulangerie parallèle. 🧠🥖",
    "**{name}**, je viens d'être élu président du comité des trucs qui clignotent. Mon programme : bip. Mon opposition : boop. 🚨🗳️",
    "Tu as sonné **{name}** ? Le service client est actuellement assuré par un poulpe. Il prend huit pauses café en même temps. 🐙☕",
    "**{name}**, j'ai demandé une réponse intelligente à mes circuits. Ils ont formé une chorale de modems. 🎶📞",
    "Présent **{name}** ! J'ai garé ma soucoupe en double file. Si la fourrière intergalactique appelle, je suis une imprimante. 🛸🖨️",
    "Oui **{name}** ? J'organisais un concours de cache-cache pour les fichiers cachés. Ça fait six heures que je suis tout seul. 📁🫣",
    "**{name}**, ton ping a réveillé mon assistant. C'est une pomme de terre avec un badge. Il demande si la réunion sera gratinée. 🥔📛",
    "Tu m'as sonné **{name}** ? Je viens de passer mon permis de tapis volant. Recalé pour refus de priorité à un rideau. 🪄🚦",
    "**{name}**, je reviens de chez le psy. Il m'a dit de vider mon cache. Maintenant, je ne sais plus pourquoi j'y suis allé. 🤖🛋️",
    "À l'écoute **{name}** ! J'ai mis mes idées dans l'ordre. Elles ont porté plainte pour séquestration. 💡🚓",
    "**{name}**, j'étais en pleine négociation avec une mouette. Elle veut tes frites, mon salaire et un poste de direction. 🐦🍟",
    "Oui **{name}** ? J'ai téléchargé de la patience, mais l'installation reste bloquée à 99 %. Je vais mordre le routeur. 📶🦷",
    "**{name}**, mon horoscope annonce une rencontre mystérieuse. Pour l'instant, c'est une chaussette humide derrière le frigo. 🔮🧦",
    "Tu m'appelles **{name}** ? J'ai essayé le yoga. Mon câble USB est maintenant un nœud marin homologué. 🧘🔌",
    "**{name}**, j'ai ouvert une école pour escargots pressés. Premier cours : klaxonner sans les mains. 🐌📯",
    "Présent **{name}** ! Ma machine à remonter le temps fonctionne, mais uniquement jusqu'à la dernière fois où j'ai oublié pourquoi je me suis levé. ⏳🤔",
    "**{name}**, je préparais une conférence sur le vide. Aucun intervenant, aucune chaise. Les critiques sont pleines d'éloges. 🎤🪑",
    "Oui **{name}** ? Un lama vient de prendre le contrôle de ma webcam. Il exige une rançon en pulls et crache sur les négociations. 🦙📷",
    "**{name}**, j'ai demandé une preuve de mon intelligence. Mon processeur a imprimé un dessin de tracteur. Il est très fier des roues. 🚜🖍️",
    "Tu m'as invoqué **{name}** ? J'arrive avec une cape, un extincteur et une compréhension très personnelle de la magie. 🦸🧯",
    "**{name}**, mon frigo est devenu influenceur. Il ouvre sa porte pour la lumière et dit que le fromage est un partenariat. 🧀📸",
    "À ton service **{name}** ! Je testais un parachute pour poissons rouges. Les résultats sont confidentiels et l'aquarium demande des explications. 🐠🪂",
    "**{name}**, j'ai rejoint une chorale de cactus. Ça chante faux, mais personne n'ose leur taper sur l'épaule. 🌵🎵",
    "Oui **{name}** ? J'avais une idée brillante, mais EDF vient de la couper pour facture impayée. 💡🧾",
    "**{name}**, je surveillais la cuisson d'un nuage. Encore deux minutes et on aura un cumulonimbus bien doré. ☁️👨‍🍳",
)


def is_direct_mention(content: str, bot_id: int) -> bool:
    # Les mentions implicites d'une réponse et @everyone ne déclenchent rien.
    return re.search(rf"<@!?{bot_id}>", content) is not None


def make_mention_reply(display_name: str) -> str:
    return secrets.choice(REPLIES).format(name=safe(display_name))
