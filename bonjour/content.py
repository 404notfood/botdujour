from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
import json
from pathlib import Path
import random
import unicodedata

from astral import Observer
from astral.sun import sunrise, sunset
import discord

from .config import Config
from .observances import occasion_for

ROOT = Path(__file__).resolve().parent.parent
DAYS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
MONTHS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre")
WISHES = (
    ("Bon courage pour cette nouvelle semaine ! Que votre lundi soit rempli d'énergie et de bonne humeur !", "Un nouveau lundi, de nouvelles possibilités : avancez à votre rythme et gardez le sourire !"),
    ("Très bon mardi, plein de sourires, de réussite et de bonnes nouvelles !", "Que ce mardi vous réserve de petites joies et de belles rencontres !"),
    ("Bon mercredi à toutes et à tous ! On garde le sourire, le week-end approche doucement ! 😄", "Déjà le milieu de semaine : prenez soin de vous et profitez de ce mercredi !"),
    ("Excellent jeudi ! Que vos projets avancent et que la bonne humeur vous accompagne !", "Un petit effort, une grande satisfaction : passez un beau jeudi !"),
    ("Bon courage pour cette dernière journée de la semaine et profitez bien de votre week-end !", "Courage pour ce vendredi ! Encore un peu de bonne humeur avant de profiter du week-end !"),
    ("Profitez pleinement de votre samedi, reposez-vous et faites le plein de bons moments !", "Un beau samedi à tous, avec du repos et de petits plaisirs !"),
    ("Doux dimanche à tous ! Faites le plein de bons moments pour la semaine à venir !", "Que votre dimanche soit paisible et rempli de sourires !"),
)
SEASONAL_TEXTS = (
    (
        "❄️ Les journées d'hiver invitent à ralentir un peu. Une boisson chaude, un bon livre ou une discussion entre amis : à chacun son petit moment de douceur ! ☕💙",
        "🧣 Un petit bonjour peut réchauffer une journée d'hiver ! Prenons des nouvelles de ceux qui comptent pour nous. 💙",
        "☕ En hiver aussi, les petits plaisirs font les belles journées : une pause, un sourire et un peu de convivialité ! ❄️",
        "❄️ Et si l'on profitait de cette journée pour partager une recette, une musique ou un souvenir qui fait sourire ? 🎶💙",
        "🛌 Aujourd'hui, c'est la **Journée internationale du stagnage sous la couette** : toute sortie du lit devra être justifiée par un café ! ☕😴",
        "⏰ Aujourd'hui, c'est la **Journée des négociations avec le réveil** : encore cinq minutes, et après on ouvre les négociations pour cinq autres. 😴",
        "🧦 Aujourd'hui, c'est la **Journée du double étage de chaussettes** : vos pieds ont demandé une isolation supplémentaire. ❄️",
        "🍫 Aujourd'hui, c'est la **Journée du chocolat chaud diplomatique** : il paraît que tout se discute mieux avec des mini-guimauves. ☕",
        "🔥 Aujourd'hui, c'est la **Journée du rapprochement stratégique avec le radiateur** : une relation chaleureuse qui mérite d'être entretenue. 😌",
        "🪟 Aujourd'hui, c'est la **Journée du dessin sur la vitre embuée** : vos talents d'artiste ont enfin trouvé leur support. 🎨",
        "🛋️ Aujourd'hui, c'est la **Journée du cumul des plaids** : aucune limite de bagages sur le canapé. 🧳",
        "🐻 Aujourd'hui, c'est la **Journée de l'hibernation à temps partiel** : présent physiquement, en veille mentalement. 😴",
        "🚶 Aujourd'hui, c'est la **Journée du grand voyage lit-canapé** : prévoyez une collation pour cette expédition. 🍪",
        "🧢 Aujourd'hui, c'est la **Journée du bonnet jusqu'aux sourcils** : le style attendra le dégel. ❄️",
        "☕ Aujourd'hui, c'est la **Journée du soufflage sur la tasse** : attention à ne pas refroidir le café jusqu'à demain. 🌬️",
        "🧤 Aujourd'hui, c'est la **Journée des mains cachées dans les manches** : les doigts sont en télétravail. 💻",
        "🔋 Aujourd'hui, c'est la **Journée de la batterie humaine à 12 %** : recharge conseillée près d'une boisson chaude. ☕",
        "🪟 Aujourd'hui, c'est la **Journée du courage derrière la fenêtre** : sortir avait l'air plus simple depuis le salon. 😅",
        "🥣 Aujourd'hui, c'est la **Journée de la soupe qui répare tout** : même la motivation, si on ajoute des croûtons. 🥖",
        "🍪 Aujourd'hui, c'est la **Journée du biscuit tombé dans le mug** : une opération de sauvetage à la petite cuillère est en cours. 🥄",
        "🥿 Aujourd'hui, c'est la **Journée de la grande carrière en chaussons** : votre salon vient de vous nommer responsable du confort. 🏆",
        "🌬️ Aujourd'hui, c'est la **Journée du vent qui réveille mieux que le café** : efficacité immédiate dès l'ouverture de la porte. 😳",
        "📅 Aujourd'hui, c'est la **Journée du printemps demandé en livraison express** : le suivi du colis indique encore « patience ». 🌷",
        "🪑 Aujourd'hui, c'est la **Journée de la chaise ensevelie sous les pulls** : quelque part dessous se trouve un meuble. 🧶",
        "🦶 Aujourd'hui, c'est la **Journée du premier orteil hors du lit** : l'éclaireur recommande un repli immédiat. 🛌",
        "☕ Aujourd'hui, c'est la **Journée du café réchauffé trois fois** : une série à rebondissements dont vous connaissez déjà la fin. 🔁",
        "🛌 Aujourd'hui, c'est la **Journée de la couette qui vous retient en otage** : les négociations avancent, mais vous restez très coopératif. 😇",
        "🧀 Aujourd'hui, c'est la **Journée du fromage qui fond plus vite que la motivation** : au moins, quelqu'un travaille efficacement. 🫕",
        "🚌 Aujourd'hui, c'est la **Journée du sprint jusqu'au bus bien au chaud** : le cardio prend tout son sens en hiver. 🏃",
        "🧶 Aujourd'hui, c'est la **Journée du pull sur le pull** : la silhouette bonhomme Michelin revient à la mode dans votre salon. 😄",
        "🌡️ Aujourd'hui, c'est la **Journée du « il fait froid, hein ? »** : une phrase, mille conversations possibles. 🗣️",
        "🚪 Aujourd'hui, c'est la **Journée de la porte refermée à la vitesse de la lumière** : le chauffage vous remercie personnellement. 🔥",
        "💇 Aujourd'hui, c'est la **Journée de la coiffure offerte par le bonnet** : résultat imprévisible, tenue exceptionnelle. 🧢",
        "📱 Aujourd'hui, c'est la **Journée du duel entre les gants et le téléphone** : votre nez envisage de répondre aux messages. 👃",
        "👃 Aujourd'hui, c'est la **Journée du nez dehors, du reste dedans** : une étude de terrain très courte. ❄️",
        "📺 Aujourd'hui, c'est la **Journée de la télécommande perdue sous le plaid** : les recherches mobilisent tout le canapé. 🔎",
        "🎬 Aujourd'hui, c'est la **Journée du film terminé les yeux fermés** : vous avez surtout apprécié la bande-son. 😴",
        "🔦 Aujourd'hui, c'est la **Journée du matin qui ressemble encore à la nuit** : le soleil aussi a dû appuyer sur « répéter ». ⏰",
        "♨️ Aujourd'hui, c'est la **Journée de la bouillotte promue meilleure amie** : fiable, discrète et toujours chaleureuse. 💙",
        "🥐 Aujourd'hui, c'est la **Journée du débat entre sortir chercher du pain et rester au chaud** : le croissant mène aux points. 🥖",
        "🌨️ Aujourd'hui, c'est la **Journée de l'excuse météorologique créative** : « risque de flocon » paraît parfaitement recevable. 😇",
        "🏆 Aujourd'hui, c'est la **Journée du record de canapé en endurance** : les juges saluent votre remarquable immobilité. 🛋️",
        "🧹 Aujourd'hui, c'est la **Journée du ménage reporté au retour des beaux jours** : on appelle ça une organisation saisonnière. 📋",
        "❄️ Aujourd'hui, c'est la **Journée de l'admiration du givre depuis l'intérieur** : superbe spectacle, placement près du radiateur recommandé. 🔥",
        "☕ Aujourd'hui, c'est la **Journée de la petite gorgée de vérification** : oui, c'est encore brûlant, comme il y a trois secondes. 😅",
        "🏰 Aujourd'hui, c'est la **Journée du château de coussins anti-froid** : l'accès se paie en biscuits. 🍪",
        "🧣 Aujourd'hui, c'est la **Journée du plaid porté comme une cape** : un super-héros du confort vient de naître. 🦸",
        "🌙 Aujourd'hui, c'est la **Journée du « déjà nuit ? »** : le ciel a clairement quitté la réunion avant tout le monde. 😄",
        "📝 Aujourd'hui, c'est la **Journée de la liste des choses à faire quand il fera moins froid** : l'écriture de la liste compte déjà comme une activité. ✍️",
        "☃️ Aujourd'hui, c'est la **Journée du bonhomme de neige imaginé au chaud** : zéro engelure, cent pour cent créativité. 🎨",
        "☕ Aujourd'hui, c'est la **Journée du bonheur mesuré en tasses** : pas besoin de calculatrice, juste d'une bouilloire. 🫖",
        "🧦 Aujourd'hui, c'est la **Journée de la chaussette disparue dans la couette** : son équipière garde espoir. 🔎",
        "🛏️ Aujourd'hui, c'est la **Journée du partage équitable de la couette** : un sujet sensible dans les relations internationales du lit. 🤝",
        "🪶 Aujourd'hui, c'est la **Journée du duvet à forte attraction gravitationnelle** : même les bonnes résolutions n'arrivent pas à décoller. 🚀",
        "💤 Aujourd'hui, c'est la **Journée du gardiennage d'oreiller** : il ne faut surtout pas le laisser seul trop longtemps. 😴",
        "👔 Aujourd'hui, c'est la **Journée de la réunion en pyjama discret** : professionnel au-dessus du bureau, confortable en dessous. 💻",
        "🥿 Aujourd'hui, c'est la **Journée du pas feutré en chaussons** : vous n'êtes pas lent, vous êtes en mode silencieux. 🤫",
        "🌡️ Aujourd'hui, c'est la **Journée du réglage éternel du chauffage** : trop froid, trop chaud, puis trop froid à nouveau. 🔄",
        "🗓️ Aujourd'hui, c'est la **Journée du compte à rebours avant les beaux jours** : regarder le calendrier plus souvent ne semble pas accélérer les choses. 🌞",
        "🍫 Aujourd'hui, c'est la **Journée du dernier carré de chocolat de secours** : l'urgence est déclarée dès qu'on passe devant le placard. 🚨",
        "😴 Aujourd'hui, c'est la **Journée de la grasse matinée mentale** : vos yeux sont ouverts, mais votre cerveau n'a pas signé la feuille de présence. 📝",
        "🫖 Aujourd'hui, c'est la **Journée du thé préparé pour se réchauffer les mains** : le boire reste une option intéressante. 👐",
        "⌨️ Aujourd'hui, c'est la **Journée du clavier trop froid pour travailler** : une expertise indépendante du plaid est demandée. 🛋️",
        "🥄 Aujourd'hui, c'est la **Journée du fond de cacao qu'on refuse d'abandonner** : la dernière cuillère mérite votre persévérance. 🍫",
    ),
    (
        "🌷 Le printemps invite à profiter des couleurs et des petits moments dehors. Une belle occasion de faire une pause et de regarder autour de soi ! 🌿",
        "🌱 Avec le printemps, les idées fleurissent aussi ! Quel petit projet vous ferait plaisir aujourd'hui ? 💚",
        "🌼 Une balade, quelques photos ou un café entre amis : les plaisirs les plus simples font parfois les meilleurs souvenirs ! ☕",
        "🌿 Profitons de cette journée pour partager un peu de bonne humeur et prendre des nouvelles de nos proches ! 🌸",
        "🌼 Aujourd'hui, c'est la **Journée du grand nettoyage commencé par une pause** : il faut d'abord établir une stratégie depuis le canapé. 🛋️",
        "🌱 Aujourd'hui, c'est la **Journée de la plante encouragée à voix haute** : elle ne répond pas, mais elle apprécie probablement le soutien. 🪴",
        "🧥 Aujourd'hui, c'est la **Journée du manteau porté le matin et regretté à midi** : la mode du printemps, c'est de transporter ses vêtements. 🌤️",
        "🤧 Aujourd'hui, c'est la **Journée du nez qui applaudit le pollen** : à tes souhaits, et bravo pour cette belle participation. 🌸",
        "🪟 Aujourd'hui, c'est la **Journée du soleil qui révèle les traces sur les vitres** : merci pour l'audit surprise. 🧽",
        "🥕 Aujourd'hui, c'est la **Journée du potager plein d'ambition** : trois graines et vous envisagez déjà l'autosuffisance. 🌱",
        "🧺 Aujourd'hui, c'est la **Journée du pique-nique avec supplément fourmis** : les invitées n'ont pas confirmé leur présence, mais elles viennent quand même. 🐜",
        "🌦️ Aujourd'hui, c'est la **Journée des quatre saisons avant le déjeuner** : le ciel teste toutes ses options. ☀️",
        "🧹 Aujourd'hui, c'est la **Journée du rangement qui ressort plus de choses qu'il n'en range** : une étape normale, paraît-il. 📦",
        "🐦 Aujourd'hui, c'est la **Journée du concert d'oiseaux sans bouton volume** : ouverture des portes à l'aube, billets non remboursables. 🎶",
        "👟 Aujourd'hui, c'est la **Journée de la petite balade devenue grand détour** : votre sens de l'orientation voulait aussi prendre l'air. 🧭",
        "🪴 Aujourd'hui, c'est la **Journée du basilic sous haute surveillance** : cette fois, promis, on lit les instructions d'arrosage. 💧",
        "🌞 Aujourd'hui, c'est la **Journée du premier rayon de soleil réservé sur le balcon** : places limitées, plaid encore accepté. 😎",
        "🧦 Aujourd'hui, c'est la **Journée du grand débat sur la fin des chaussettes** : le carrelage vote pour leur maintien. 🦶",
        "🌷 Aujourd'hui, c'est la **Journée du bouquet qui prend toute la table** : déjeuner debout devient un choix décoratif. 💐",
        "☔ Aujourd'hui, c'est la **Journée du parapluie oublié juste avant l'averse** : votre mémoire a un sens du spectacle remarquable. 🌧️",
        "🧑‍🌾 Aujourd'hui, c'est la **Journée du jardinier de rebord de fenêtre** : votre exploitation compte deux pots et beaucoup d'espoir. 🌱",
        "📷 Aujourd'hui, c'est la **Journée des vingt photos de la même fleur** : elle n'avait pourtant demandé qu'un portrait. 🌸",
        "🦋 Aujourd'hui, c'est la **Journée du papillon suivi du regard jusqu'à oublier sa phrase** : une interruption tout à fait poétique. 😄",
        "🚲 Aujourd'hui, c'est la **Journée du vélo ressorti et des pneus dégonflés** : la promenade commence par une séance de musculation des bras. 💪",
        "🕶️ Aujourd'hui, c'est la **Journée des lunettes de soleil perdues sur la tête** : les recherches approchent de leur dénouement. 🔎",
        "🌿 Aujourd'hui, c'est la **Journée du « je prends juste un petit plant »** : le retour de jardinerie nécessite finalement un coffre plus grand. 🚗",
        "🐝 Aujourd'hui, c'est la **Journée de la négociation avec l'abeille près du goûter** : elle souhaite simplement consulter le menu. 🍯",
        "🪁 Aujourd'hui, c'est la **Journée du vent qui choisit votre coiffure** : prestation gratuite, résultat sans garantie. 💇",
        "👕 Aujourd'hui, c'est la **Journée du tee-shirt optimiste** : le soleil était là au moment de s'habiller, votre honneur est sauf. 🥶",
        "🧽 Aujourd'hui, c'est la **Journée de l'éponge retrouvée après la motivation** : elles ne sont jamais disponibles en même temps. 😅",
        "🌱 Aujourd'hui, c'est la **Journée de la pousse inspectée toutes les dix minutes** : grandir sous pression n'a pourtant jamais été simple. 🔎",
        "🍓 Aujourd'hui, c'est la **Journée de la fraise testée pour vérifier la qualité du panier** : un contrôle sérieux exige plusieurs échantillons. 😋",
        "🧺 Aujourd'hui, c'est la **Journée du linge étendu sous surveillance météo** : votre nouveau sport consiste à regarder les nuages. ☁️",
        "🧴 Aujourd'hui, c'est la **Journée du ménage parfum prairie** : une façon de sortir prendre l'air sans quitter le salon. 🌼",
        "🧢 Aujourd'hui, c'est la **Journée du chapeau qui part en promenade tout seul** : le vent lui a proposé un covoiturage. 🌬️",
        "🐌 Aujourd'hui, c'est la **Journée de la course d'escargots intérieure** : côté motivation, la compétition est serrée. 🏁",
        "🌸 Aujourd'hui, c'est la **Journée du calendrier rempli d'envies de sorties** : reste à prévenir l'agenda qu'il doit libérer de la place. 📅",
        "🛋️ Aujourd'hui, c'est la **Journée du printemps admiré depuis le canapé** : observer la nature reste une activité de plein regard. 👀",
        "🥪 Aujourd'hui, c'est la **Journée du sandwich mangé dehors avec vue sur le bureau** : les vacances commencent parfois modestement. 🌳",
        "🪴 Aujourd'hui, c'est la **Journée du rempotage avec décoration du sol** : le terreau voulait aussi découvrir la maison. 🧹",
        "🌧️ Aujourd'hui, c'est la **Journée du bruit de pluie qui annule la course à pied** : quel dommage, les baskets étaient presque motivées. 👟",
        "🧥 Aujourd'hui, c'est la **Journée du rangement des affaires d'hiver provisoire** : la couette attend votre rappel dans le couloir. 🛌",
        "📚 Aujourd'hui, c'est la **Journée du livre ouvert au soleil et jamais lu** : on a surtout étudié les nuages. ☁️",
        "🐞 Aujourd'hui, c'est la **Journée de la coccinelle nommée mascotte du balcon** : félicitations pour cette belle promotion. 🏅",
        "🌿 Aujourd'hui, c'est la **Journée de la ciboulette coupée comme chez le coiffeur** : un peu plus court sur les côtés, s'il vous plaît. ✂️",
        "🪟 Aujourd'hui, c'est la **Journée de la fenêtre ouverte et du papier envolé** : vos documents prennent enfin leur indépendance. 📄",
        "😴 Aujourd'hui, c'est la **Journée de la sieste de printemps** : la nature se réveille, vous équilibrez les statistiques. 🌷",
        "🌈 Aujourd'hui, c'est la **Journée du rayon de soleil entre deux réunions** : le ciel a réussi à trouver un créneau. 📅",
    ),
    (
        "🌞 L'été invite à savourer les petits moments : une promenade, une discussion entre amis ou une pause au calme. Profitez de ce qui vous fait du bien ! 💛",
        "🌻 Et si l'on gardait un peu de temps aujourd'hui pour une activité qui nous plaît ? Les petits plaisirs comptent aussi ! 💙",
        "🍉 Une idée de sortie, une recette à partager ou simplement un bonjour : faisons circuler la bonne humeur ! 🌞",
        "🌅 Prenons le temps d'apprécier un joli paysage ou un moment de calme. Parfois, quelques minutes suffisent pour se changer les idées ! 💛",
        "🌀 Aujourd'hui, c'est la **Journée du tête-à-tête avec le ventilateur** : une relation qui tourne rond. 😎",
        "🍦 Aujourd'hui, c'est la **Journée de la glace mangée avant qu'elle ne prenne la fuite** : pour une fois, la gourmandise est une urgence. 🏃",
        "🌳 Aujourd'hui, c'est la **Journée de la réservation du dernier coin d'ombre** : votre serviette possède désormais un titre de propriété. 📜",
        "🧊 Aujourd'hui, c'est la **Journée de la visite culturelle du réfrigérateur** : exposition temporaire, portes à refermer après la visite. 😄",
        "🏊 Aujourd'hui, c'est la **Journée de la piscine imaginée depuis le bureau** : en attendant, le fond d'écran fait ce qu'il peut. 💻",
        "🩴 Aujourd'hui, c'est la **Journée de la tong qui annonce votre arrivée** : impossible d'entrer discrètement dans une pièce. 👣",
        "🏖️ Aujourd'hui, c'est la **Journée du sable invité à la maison** : il prévoit de rester dans vos chaussures jusqu'en décembre. 👟",
        "🧺 Aujourd'hui, c'est la **Journée de la serviette oubliée en partant à la plage** : l'organisation était presque parfaite. 😅",
        "😴 Aujourd'hui, c'est la **Journée de la sieste en format long métrage** : le réveil a été repoussé pour raisons artistiques. 🎬",
        "🛏️ Aujourd'hui, c'est la **Journée du côté frais de l'oreiller** : une découverte qui mérite au moins une petite médaille. 🥇",
        "🦟 Aujourd'hui, c'est la **Journée du concert de moustique près de l'oreille** : un seul musicien, beaucoup trop de rappels. 🎻",
        "🍉 Aujourd'hui, c'est la **Journée de la pastèque qui occupe tout le frigo** : les yaourts réclament une réunion de copropriété. 🥛",
        "🎯 Aujourd'hui, c'est la **Journée de la pétanque commentée comme une finale mondiale** : même le cochonnet ressent la pression. 🏆",
        "👜 Aujourd'hui, c'est la **Journée du sac de plage sans fond** : on y trouve tout, sauf ce qu'on cherche. 🔎",
        "🧳 Aujourd'hui, c'est la **Journée de la valise préparée mentalement** : concrètement, elle est encore sur l'armoire. ✈️",
        "🌴 Aujourd'hui, c'est la **Journée du message d'absence rêvé** : « parti vérifier la température de la mer, retour à déterminer ». 📩",
        "☕ Aujourd'hui, c'est la **Journée de la pause terrasse à rallonge** : le café est terminé, la contemplation continue. 😎",
        "🍋 Aujourd'hui, c'est la **Journée de la limonade très sérieusement dégustée** : quelqu'un doit bien assurer le contrôle des glaçons. 🧊",
        "🔥 Aujourd'hui, c'est la **Journée du barbecue commenté par tout le voisinage** : un cuisinier, douze experts autour de la grille. 🌭",
        "📖 Aujourd'hui, c'est la **Journée du livre de vacances qui bronze davantage qu'il n'est lu** : lui aussi avait besoin de repos. 🏖️",
        "🕶️ Aujourd'hui, c'est la **Journée de la marque de lunettes imaginaire** : votre visage songe à lancer sa propre collection. 😄",
        "🚗 Aujourd'hui, c'est la **Journée du « on arrive bientôt ? »** : une tradition automobile dont personne ne connaît la fin. 🛣️",
        "🗺️ Aujourd'hui, c'est la **Journée du détour touristique involontaire** : se perdre devient tout de suite plus chic avec ce nom. 🧭",
        "🍅 Aujourd'hui, c'est la **Journée de la tomate qui s'échappe du sandwich** : votre tee-shirt vient de recevoir un souvenir de pique-nique. 🥪",
        "🪑 Aujourd'hui, c'est la **Journée du transat aux réglages mystérieux** : le mode d'emploi semble réservé aux ingénieurs. 🔧",
        "🌅 Aujourd'hui, c'est la **Journée du coucher de soleil photographié vingt fois** : le ciel a encore livré une belle prestation. 📷",
        "🏰 Aujourd'hui, c'est la **Journée du château de sable ambitieux** : le permis de construire est validé jusqu'à la prochaine vague. 🌊",
        "🧢 Aujourd'hui, c'est la **Journée de la casquette portée par principe de vacances** : même pour aller sortir les poubelles. 😎",
        "🍑 Aujourd'hui, c'est la **Journée du fruit juteux mangé au-dessus de l'évier** : le glamour des beaux jours dans toute sa splendeur. 😋",
        "📱 Aujourd'hui, c'est la **Journée du téléphone rangé pour profiter du paysage** : après juste une dernière photo, évidemment. 📷",
        "🦆 Aujourd'hui, c'est la **Journée de la bouée gonflable trop imposante** : elle voyage presque aussi confortablement que vous. 🚗",
        "⛱️ Aujourd'hui, c'est la **Journée du parasol déplacé toutes les dix minutes** : le soleil refuse toujours de rester à sa place. 🌞",
        "🧦 Aujourd'hui, c'est la **Journée des chaussettes officiellement en congé** : elles vous ont laissé leurs salutations depuis le tiroir. 🩴",
        "🍨 Aujourd'hui, c'est la **Journée du choix impossible entre deux parfums de glace** : la solution diplomatique tient dans deux boules. 🤝",
        "🌊 Aujourd'hui, c'est la **Journée du pied dans l'eau suivi d'un grand discours** : « une fois dedans, elle est bonne », paraît-il. 🥶",
        "🎒 Aujourd'hui, c'est la **Journée de la promenade soi-disant toute plate** : le sentier n'a manifestement pas reçu le même programme. 🥾",
        "🧊 Aujourd'hui, c'est la **Journée du glaçon qui disparaît avant la première gorgée** : une carrière brève, mais rafraîchissante. 🥤",
        "🪟 Aujourd'hui, c'est la **Journée de la chasse au courant d'air** : les portes participent en claquant avec enthousiasme. 🌬️",
        "🌴 Aujourd'hui, c'est la **Journée des vacances du cerveau** : votre corps est au bureau, le reste cherche une place près de la mer. 🏖️",
        "🎶 Aujourd'hui, c'est la **Journée du tube de l'été coincé dans la tête** : impossible de désabonner votre cerveau de cette radio. 📻",
        "🥗 Aujourd'hui, c'est la **Journée de la salade qui voulait devenir un repas complet** : les croûtons ont immédiatement pris les commandes. 🥖",
        "🚶 Aujourd'hui, c'est la **Journée du déplacement à vitesse estivale** : vous avancez lentement pour ne pas froisser les vacances. 😌",
        "📆 Aujourd'hui, c'est la **Journée du calendrier consulté avant chaque pause** : techniquement, le départ en vacances se rapproche à chaque café. ☕",
        "⭐ Aujourd'hui, c'est la **Journée de l'observation des étoiles en pyjama** : pas besoin de tenue de gala pour admirer le ciel. 🌌",
    ),
    (
        "🍂 Les journées raccourcissent en automne : c'est l'occasion de profiter d'un peu de douceur et de convivialité ! Une boisson chaude et un moment entre amis, ça fait toujours plaisir. ☕🍁",
        "🍁 L'automne nous offre de belles couleurs à admirer. Et si l'on prenait quelques minutes pour une promenade ou une jolie photo ? 📷🍂",
        "☕ Les soirées d'automne se prêtent aux petits plaisirs : un livre, un jeu ou une discussion entre amis. Quel est votre programme idéal ? 🍂💙",
        "🍂 Une recette réconfortante, une musique qu'on aime et un peu de temps pour soi : de quoi apporter de la douceur à cette journée d'automne ! 🎶🍁",
        "🛌 Aujourd'hui, c'est la **Journée du retour officiel sous la couette** : la commission du confort a voté à l'unanimité. 😴",
        "🍂 Aujourd'hui, c'est la **Journée de la feuille qui craque sous la chaussure** : un petit concert gratuit à chaque pas. 👟",
        "🛋️ Aujourd'hui, c'est la **Journée de la fusion avec le canapé** : toute tentative de séparation nécessitera un goûter. 🍪",
        "☔ Aujourd'hui, c'est la **Journée du parapluie retourné par le vent** : le modèle antenne satellite est très tendance cette année. 📡",
        "🧣 Aujourd'hui, c'est la **Journée de l'écharpe ressortie avec émotion** : vous aviez tant de choses à vous raconter depuis le printemps. 💙",
        "🍄 Aujourd'hui, c'est la **Journée du champignon photographié avec prudence** : pour le dîner, les pâtes du placard semblent plus coopératives. 🍝",
        "🎃 Aujourd'hui, c'est la **Journée de la citrouille au regard de travers** : votre talent de sculpteur a surtout produit de la personnalité. 😄",
        "📦 Aujourd'hui, c'est la **Journée du carton de pulls introuvable** : il est probablement derrière les bonnes résolutions du rangement. 🧶",
        "🌧️ Aujourd'hui, c'est la **Journée de la pluie qui tombe à l'heure de sortir** : la synchronisation mérite des applaudissements. 👏",
        "🥣 Aujourd'hui, c'est la **Journée de la soupe préparée pour tout l'immeuble** : la petite casserole était une mauvaise estimation. 🥕",
        "🧦 Aujourd'hui, c'est la **Journée de la chaussette épaisse retrouvée au fond du tiroir** : les retrouvailles s'annoncent chaleureuses. 🥰",
        "🫖 Aujourd'hui, c'est la **Journée du thé qui accompagne absolument tout** : lecture, discussion, contemplation du thé suivant… ☕",
        "🌰 Aujourd'hui, c'est la **Journée du marron ramassé sans raison précise** : il rejoint le petit musée de votre poche. 🏛️",
        "📖 Aujourd'hui, c'est la **Journée du roman et du plaid en réunion privée** : merci de ne déranger qu'en cas de biscuits disponibles. 🍪",
        "🪟 Aujourd'hui, c'est la **Journée du regard dramatique sur la pluie** : votre clip musical intérieur vient de commencer. 🎵",
        "🥾 Aujourd'hui, c'est la **Journée de la flaque plus profonde que prévu** : votre chaussure vient de suivre un stage de natation. 🏊",
        "🧥 Aujourd'hui, c'est la **Journée du manteau porté ouvert, puis fermé, puis ouvert** : la météo adore les activités manuelles. 🌦️",
        "🐿️ Aujourd'hui, c'est la **Journée des réserves de biscuits pour l'hiver** : l'écureuil approuve la démarche, moins le rythme de consommation. 🍪",
        "🧹 Aujourd'hui, c'est la **Journée des feuilles balayées qui reviennent** : le vent souhaite une deuxième manche. 🍂",
        "⏰ Aujourd'hui, c'est la **Journée de la motivation restée à l'heure d'été** : elle vous rejoindra après un petit café. ☕",
        "🍎 Aujourd'hui, c'est la **Journée de la tarte aux pommes pour raison météorologique** : on ne discute pas les décisions du goûter. 🥧",
        "🕯️ Aujourd'hui, c'est la **Journée de l'ambiance cosy organisée très sérieusement** : votre salon attend sa cinquième étoile. ⭐",
        "👻 Aujourd'hui, c'est la **Journée du fantôme en panne de motivation** : même son « bouh » est parti faire une sieste. 😴",
        "🧶 Aujourd'hui, c'est la **Journée du pull dont les manches mangent les mains** : pratique pour transporter discrètement de la chaleur. 👐",
        "🛏️ Aujourd'hui, c'est la **Journée de la couette remise à sa place** : sur le lit, sur le canapé, sur vous… elle est très polyvalente. 🏆",
        "📺 Aujourd'hui, c'est la **Journée de l'épisode supplémentaire absolument nécessaire** : l'automne a signé une autorisation exceptionnelle. 🎬",
        "🍵 Aujourd'hui, c'est la **Journée de la tasse gardée à deux mains** : ce n'est plus une boisson, c'est un équipement de confort. 🧤",
        "🍁 Aujourd'hui, c'est la **Journée du détour pour marcher dans les feuilles** : le GPS ne comprend pas, mais les chaussures sont ravies. 👟",
        "🧺 Aujourd'hui, c'est la **Journée du linge qui sèche à son rythme** : lui aussi réclame un peu de patience et de bienveillance. 😌",
        "🧅 Aujourd'hui, c'est la **Journée de l'habillage façon oignon** : chaque nouvelle couche est une petite décision de survie au matin frais. 🧥",
        "☁️ Aujourd'hui, c'est la **Journée du nuage garé devant votre fenêtre** : il semble attendre quelqu'un depuis ce matin. 🚗",
        "🎮 Aujourd'hui, c'est la **Journée du grand voyage sans quitter le fauteuil** : une manette suffit parfois à organiser l'évasion. 🗺️",
        "🥧 Aujourd'hui, c'est la **Journée du gâteau encore tiède qui attire tout le monde** : le parfum a envoyé les invitations à votre place. 😋",
        "📷 Aujourd'hui, c'est la **Journée de la photo de forêt qui devient fond d'écran** : le bureau aussi avait besoin de prendre l'air. 🍂",
        "🦔 Aujourd'hui, c'est la **Journée du mode hérisson** : on se roule dans le plaid et on observe discrètement la situation. 👀",
        "🔎 Aujourd'hui, c'est la **Journée de la recherche du deuxième chausson** : le canapé est une nouvelle fois entendu comme témoin. 🛋️",
        "🧇 Aujourd'hui, c'est la **Journée de la gaufre qui console du ciel gris** : une solution avec des petites cases pour le chocolat. 🍫",
        "🚶 Aujourd'hui, c'est la **Journée de la promenade écourtée par le souvenir du canapé** : savoir rentrer, c'est aussi savoir s'organiser. 😇",
        "🎵 Aujourd'hui, c'est la **Journée de la playlist d'automne trop dramatique** : vous alliez juste chercher le pain, pas tourner une fin de film. 🥖",
        "📝 Aujourd'hui, c'est la **Journée du projet commencé après le goûter** : le goûter n'a pas encore de date de fin officielle. 🍪",
        "🌬️ Aujourd'hui, c'est la **Journée du vent qui pousse dans le mauvais sens** : même la météo a décidé de vous faire travailler les jambes. 🦵",
        "🪑 Aujourd'hui, c'est la **Journée du fauteuil réservé au plaid** : vous pouvez vous asseoir, mais seulement en sa compagnie. 🤝",
        "🥄 Aujourd'hui, c'est la **Journée de la compote goûtée directement dans la casserole** : une inspection exigeante, cuillère après cuillère. 🍎",
        "🐈 Aujourd'hui, c'est la **Journée du chat nommé directeur de la sieste** : son expérience du poste ne souffre aucune contestation. 😴",
    ),
)
BOLD_CAPITALS = str.maketrans({chr(65 + i): chr(0x1D400 + i) for i in range(26)})


def safe(text: str) -> str:
    return discord.utils.escape_markdown(discord.utils.escape_mentions(text.replace("\n", " ")))


def marker(day: date) -> str:
    # Ancien pied de message, encore reconnu dans l'historique.
    return f"Bulletin du {day.isoformat()}"


def date_line(day: date) -> str:
    return f"📅 **Nous sommes le {DAYS[day.weekday()]} {day.day} {MONTHS[day.month - 1]} {day.year}**"


def heading(text: str) -> str:
    return unicodedata.normalize("NFD", text.upper()).translate(BOLD_CAPITALS)


def editorial(text: str) -> str:
    """Autoriser le gras éditorial, en protégeant toujours les mentions et le reste du Markdown."""
    lines = []
    for line in text.splitlines():
        parts = line.split("**")
        # Ne pas produire de gras non refermé si le calendrier contient une coquille.
        lines.append("**".join(safe(part) for part in parts) if len(parts) % 2 else safe(line))
    return "\n".join(lines)


def _occasion(day: date, data: dict) -> dict | None:
    event = (data["dates"].get(day.isoformat()) or data["annual"].get(day.strftime("%m-%d"))
             or occasion_for(day))
    # Le thème mensuel est un rappel du lundi, pas le même bulletin tous les jours.
    return event or (data["months"].get(str(day.month)) if day.weekday() == 0 else None)


def occasion(day: date) -> dict | None:
    return _occasion(day, json.loads((ROOT / "calendar.json").read_text(encoding="utf-8")))


@lru_cache(maxsize=16)
def _missing_dates(year: int, season: int, calendar_text: str) -> tuple[date, ...]:
    data = json.loads(calendar_text)
    first = date(year, 1, 1)
    days = (first + timedelta(days=offset) for offset in range((date(year + 1, 1, 1) - first).days))
    return tuple(day for day in days if (day.month % 12) // 3 == season and _occasion(day, data) is None)


def seasonal_text(day: date) -> str:
    """Un tirage sans remise par saison et par année, stable après redémarrage."""
    season = (day.month % 12) // 3
    calendar_text = (ROOT / "calendar.json").read_text(encoding="utf-8")
    missing = _missing_dates(day.year, season, calendar_text)
    # Les vrais événements ne consomment pas de texte humoristique.
    position = missing.index(day)
    texts = list(SEASONAL_TEXTS[season])
    random.Random(f"petit-mot:{day.year}:{season}").shuffle(texts)
    # Un calendrier modifié reste utilisable même s'il finit par épuiser la banque.
    return texts[position % len(texts)]


def clock_notice(day: date, zone) -> list[str]:
    def offset(on_day):
        return datetime.combine(on_day, time(12), zone).utcoffset()

    current = offset(day)
    tomorrow = offset(day + timedelta(days=1))
    if tomorrow != current:
        winter = tomorrow < current
        title = heading("ATTENTION : CHANGEMENT D'HEURE !")
        return [
            f"⏰ **・{title}** 🕰️",
            f"🌙 Cette nuit, nous passons à **l'heure {'d’hiver' if winter else 'd’été'}** !",
            "À 3h du matin, il sera 2h. Une heure de sommeil en plus ! 😴" if winter else
            "À 2h du matin, il sera 3h. Pensez à avancer vos horloges d'une heure ! ⏰",
        ]
    yesterday = offset(day - timedelta(days=1))
    if yesterday != current:
        winter = current < yesterday
        return [
            f"🕰️ **Nous sommes passés à l'heure {'d’hiver' if winter else 'd’été'} !**",
            "⏰ Cette nuit, à 3h du matin, il était 2h. Une heure de sommeil en plus ! 😴" if winter else
            "⏰ Cette nuit, à 2h du matin, il était 3h. Pensez à vérifier vos horloges !",
        ]
    return []


def render(config: Config, day: date, names: list[str] | None) -> str:
    observer = Observer(config.latitude, config.longitude)
    rise = sunrise(observer, date=day, tzinfo=config.timezone)
    setting = sunset(observer, date=day, tzinfo=config.timezone)
    minutes = round((setting.astimezone(timezone.utc) - rise.astimezone(timezone.utc)).total_seconds() / 60)
    lines = [
        f"🤖 **・{heading('BONJOUR À TOUS !')}** 🌞",
        "━━━━━━━━━━━━━━━━━━━━━━",
        date_line(day),
        *clock_notice(day, config.timezone),
        f"🌅 **Lever du soleil :** {rise:%Hh%M}",
        f"🌇 **Coucher du soleil :** {setting:%Hh%M}",
        f"⏳ **Durée du jour :** {minutes // 60}h{minutes % 60:02d}",
    ]
    event = occasion(day)
    if event:
        lines.extend([f"🌍 **・{heading(safe(event['title']))}**", editorial(event["text"])])
    else:
        lines.extend([f"🌍 **・{heading('LE PETIT MOT DU JOUR')}**", editorial(seasonal_text(day))])
    lines.append(f"🎉 **・{heading('FÊTE DU JOUR')}**")
    if names:
        # Le lien sur la fleur crédite Nominis sans ajouter de pied technique au bulletin.
        lines.append(f"[💐](<https://nominis.cef.fr>) Bonne fête aux **{safe(names[0])}** !")
    else:
        lines.append("💐 Le calendrier des prénoms est indisponible aujourd'hui.")
    # Choix stable par date pour garder le même aperçu après un redémarrage.
    wish = random.Random(day.isoformat()).choice(WISHES[day.weekday()])
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    if day.weekday() == 4:
        lines.append(f"🎉 **{heading('ENFIN VENDREDI !')}**")
    lines.extend([f"✨ {wish} 💙", "🤖 *Votre bot vous souhaite une excellente journée !* 🌞"])
    message = "\n".join(lines)
    if len(message.encode("utf-16-le")) // 2 > 2000:
        raise ValueError("Le bulletin dépasse la limite Discord de 2 000 caractères. Raccourcir calendar.json.")
    return message
