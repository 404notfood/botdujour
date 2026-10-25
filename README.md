# Bot du jour — Discord

Bot Python pour Debian 13 : un bulletin en français dans **un serveur et un salon configurés**, chaque matin entre **08:00 et 09:00, heure de Paris**. L'heure est tirée au sort chaque jour, à la minute, puis conservée dans SQLite. La vérification a lieu toutes les 30 secondes : l'envoi peut donc suivre la minute choisie de quelques secondes.

`Europe/Paris` gère les heures d'été et d'hiver, indépendamment du fuseau du VPS. Ne pas remplacer ce fuseau par un décalage fixe UTC+1 ou UTC+2.

## Contenu

- Date française, soleil et durée du jour calculés localement avec Astral.
- **Paris sert de référence pour le soleil.** Il n'existe pas un seul horaire valable pour toute la France métropolitaine. La ville et ses coordonnées sont modifiables.
- Fête du jour via l'[API officielle Nominis](https://nominis.cef.fr/contenus/integrations.html), avec cache par date. Le premier prénom principal renvoyé est affiché en gras ; l'emoji 💐 contient le lien de crédit vers Nominis. Ce calendrier peut différer du calendrier des fleuristes. En cas de panne et sans cache, le bot affiche que les prénoms sont indisponibles.
- Journées du [calendrier officiel de l'ONU](https://www.un.org/fr/observances/list-days-weeks), conservées localement dans `un_calendar.json` : 239 entrées relevées le 21 octobre 2026, avec titres stylisés, emojis et noms des journées en gras. Les dates mobiles sont recalculées ; la Journée mondiale de la statistique revient tous les cinq ans. Plusieurs journées peuvent être présentées ensemble. Les textes d'accompagnement sont rédigés pour ce bot.
- Textes personnalisés et journées complémentaires dans `calendar.json`, prioritaires sur le calendrier ONU. Le thème mensuel, comme Octobre rose, revient uniquement le lundi sans événement prioritaire. Les dates sans événement reçoivent chacune un petit mot de saison ou une journée humoristique inventée par le bot, comme la « Journée internationale du stagnage sous la couette ».
- 208 petits mots dans `SEASONAL_TEXTS` : 64 pour l'hiver et 48 pour chaque autre saison. Ils sont mélangés par saison et par année, puis attribués uniquement aux dates sans événement, sans répétition avant épuisement de la banque. Le calendrier fourni permet une phrase différente pour chaque date manquante de l'année. Le choix reste stable après redémarrage ; modifier le calendrier peut redistribuer les phrases. Si un calendrier personnalisé épuise une banque, la rotation reprend au début.
- Rappel du changement d'heure la veille et le jour même, calculé avec `Europe/Paris`, et titre « ENFIN VENDREDI ! » le vendredi.
- Une formule de bonne journée adaptée au jour de la semaine, parmi deux variantes par jour, choisie de façon stable pour une date donnée.
- Réponse à un message commençant par une salutation (« bonjour », « bonsoir », « salut », « coucou », « hey », « hello », « hi », « yo », « ola » ou « hola », avec leurs variantes accentuées), avec le pseudo du membre sur le serveur et une phrase polie et humoristique. Une seule réponse par membre et par jour, tous salons confondus, selon la date de Paris ; le suivi persiste après redémarrage.
- Relances du salon du bulletin après deux heures sans message humain, puis toutes les deux heures si le silence continue : humour léger ou noir, petit ASCII ou message binaire à décrypter. Envois entre 09:00 et 22:00, heure de Paris.
- Invitation à rejoindre les membres présents dans les vocaux publics, ajoutée aux relances lorsque des salons sont occupés et accessibles.
- Annonce dans le salon du bulletin à chaque arrivée d'un membre en vocal public, même sans inactivité, avec le salon cliquable et les autres membres présents.
- Aucun service d'IA ni clé d'API payante. Les salutations nécessitent la lecture des nouveaux messages ; leur contenu et les pseudos ne sont pas enregistrés dans la base.

## 1. Créer l'application Discord

1. Ouvrir le [portail développeur Discord](https://discord.com/developers/applications), créer une application puis son bot.
2. Dans la page **Bot**, récupérer le token et le conserver uniquement dans `.env`. Ne pas le publier ou l'envoyer dans un chat. Si le token a été divulgué, le réinitialiser.
3. Dans **OAuth2 → URL Generator**, choisir `bot` et `applications.commands`.
4. Accorder uniquement **Voir le salon**, **Envoyer des messages** et **Voir les anciens messages**. Pas besoin de la permission Administrateur. Dans **Bot → Privileged Gateway Intents**, activer **Message Content Intent** pour les réponses aux « bonjour » (activées par défaut dans le code). L'intent des membres et celui des présences ne sont pas nécessaires. Si les salutations sont désactivées dans la configuration, Message Content Intent n'est plus demandé.
5. Utiliser le lien d'invitation pour ajouter le bot au serveur voulu. Vérifier également les permissions spécifiques du salon.
6. Dans Discord, activer **Paramètres utilisateur → Avancés → Mode développeur**. Clic droit sur le serveur → **Copier l'identifiant du serveur**, puis sur le salon → **Copier l'identifiant du salon**.

Le salon doit être un salon textuel classique ou d'annonces, pas un fil, un forum, une catégorie ou un message privé.

Pour l'invitation simple, laisser **Requires OAuth2 Code Grant** désactivé dans la rubrique **Bot → Authorization Flow**.

## 2. Installation Debian 13

Le projet est installé directement dans `/home/bot/app` et le service fonctionne avec l'utilisateur existant `bot`, qui n'a pas besoin de sudo. Les commandes système s'exécutent depuis le compte administrateur `debian`, avec sudo. Le shell interactif de `bot` peut être isolé avec Bubblewrap (`vps-shell-bot`) : dans ce cas, ne pas y lancer systemctl. Le service système lance directement Python sous l'identité de bot, sans ouvrir ce shell. Ne pas transférer un environnement `.venv` Windows sur Debian : le créer sur le VPS.

Avec **debian**, préparer les dépendances système et les dossiers de données :

```bash
sudo apt update
sudo apt install -y python3 python3-venv tzdata ca-certificates
sudo install -d -o bot -g bot -m 750 /var/lib/botdujour /home/bot/app/data
```

Avec **bot**, installer les bibliothèques Python et remplir la configuration. Depuis debian, utiliser `sudo -iu bot` pour ouvrir cette session :

```bash
cd /home/bot/app
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp -n config.example.json config.json
cp -n .env.example .env
nano config.json
nano .env
```

Les copies avec `cp -n` préservent une configuration déjà renseignée.

Dans `config.json`, mettre les vrais identifiants **entre guillemets**. Pour une nouvelle installation, utiliser `/var/lib/botdujour/bot.sqlite3` pour `state_db`. Si une base existe déjà dans `data/bot.sqlite3`, conserver ce chemin pour préserver les envois mémorisés ; le service autorise également ce dossier :

```json
{
  "guild_id": "123456789012345678",
  "channel_id": "234567890123456789",
  "timezone": "Europe/Paris",
  "send_window": {"start": "08:00", "end": "09:00"},
  "location": {"name": "Paris", "latitude": 48.8566, "longitude": 2.3522},
  "state_db": "/var/lib/botdujour/bot.sqlite3"
}
```

Les identifiants ci-dessus sont fictifs. Dans `.env`, remplacer `votre_token_discord` par le token du bot, sans espace autour du `=`.

```bash
chmod 600 .env config.json
.venv/bin/python bot.py --check
.venv/bin/python bot.py --preview --date 2026-10-19
```

`--check` valide les fichiers et le rendu du jour sans se connecter à Discord. L'aperçu appelle Nominis, écrit son cache dans la base et affiche le message dans le terminal ; il ne publie rien sur Discord. Pour un aperçu sans réseau, ajouter `--offline` (les prénoms seront indiqués comme indisponibles).

## 3. Démarrage automatique

Revenir à **debian** avec `exit`, puis installer et démarrer le service :

```bash
sudo systemctl unmask botdujour
sudo cp /home/bot/app/deploy/botdujour.service /etc/systemd/system/botdujour.service
sudo systemctl daemon-reload
sudo systemctl reset-failed botdujour
sudo systemctl enable --now botdujour
sudo systemctl status botdujour
sudo journalctl -u botdujour -f
```

Le service utilise `User=bot`, `WorkingDirectory=/home/bot/app` et `ProtectHome=read-only` afin de pouvoir lire le projet situé dans `/home`. Seuls `/var/lib/botdujour` et `/home/bot/app/data` sont ouverts en écriture persistante pour les bases. Ne pas réutiliser l'ancien service pointant vers `/opt/botdujour` ou `/home/bot/app/botdujour`, ou avec `ProtectHome=true`.

Le service démarre avec le VPS et redémarre après un échec. Les journaux signalent la connexion, les permissions, l'heure choisie en heure de Paris et les envois. Le préfixe des journaux suit éventuellement le fuseau du système ; l'heure annoncée pour le bulletin est toujours celle de Paris. Il suffit de connexions sortantes HTTPS et WebSocket vers Discord, et HTTPS vers Nominis ; aucun port entrant n'est nécessaire.

La commande Discord **`/bonjour-apercu`** affiche le bulletin uniquement à son auteur. Elle exige la permission **Gérer le serveur**, vérifiée également à l'exécution. Aucun bouton ni commande ne provoque un envoi public de test.

## Réponses aux salutations

Un membre qui écrit « Bonjour », « Bonsoir à tous ! », « Hey », « Hello », « Ola » ou « 👋 Salut » reçoit une réponse dans le même salon, par exemple :

> Bonjour **Alex** ! Bien dormi ? J'ai demandé au café de te réveiller doucement. Il a sorti un mégaphone. ☕📣

La phrase est tirée au sort dans la banque du moment, **à l'heure de Paris** : matin de 05:00 à 11:59, midi de 12:00 à 13:59, après-midi de 14:00 à 17:59, soirée de 18:00 à 04:59. Par exemple, le bot souhaite bon appétit à midi et parle de détente le soir. Les changements d'heure sont pris en compte. Ces créneaux adaptent les réponses ; ils n'ajoutent pas de publications automatiques à heures fixes.

Les salutations reconnues sont « bonjour », « bonsoir », « salut », « coucou », « hey », « hello », « hi », « yo », « ola », « olà », « olá », « hola » et « holà ». La détection accepte les majuscules, les espaces initiaux, le gras avec des astérisques et un emoji 👋 avant la salutation. Le mot doit être complet et placé en début de message.

Le bot utilise le pseudo affiché sur le serveur (`display_name`), sans notification de mention. Il ignore les autres bots, les webhooks, les messages privés, les autres serveurs et une salutation simplement citée au milieu d'un message. Il ne répond pas non plus aux modifications de messages.

La limite est **une réponse par personne et par jour civil, à l'heure de Paris**, et s'applique même si la personne change de salon ou de pseudo. Deux personnes avec le même pseudo ont chacune leur réponse. L'identifiant Discord est utilisé pour ce suivi, qui reste enregistré dans la même base SQLite que les bulletins. Le lendemain commence à minuit à Paris, changements d'heure inclus.

Les salutations sont actives par défaut, y compris avec les anciens fichiers de configuration. Pour les désactiver ou les restreindre à certains salons, ajouter ce bloc dans `config.json` (en conservant les autres paramètres) :

```json
"greetings": {
  "enabled": true,
  "channel_ids": []
}
```

Une liste vide autorise tous les salons accessibles du serveur configuré. Pour restreindre les réponses, mettre les identifiants exacts, par exemple `"channel_ids": ["234567890123456789"]`. Pour un fil, utiliser son propre identifiant. `channel_id` reste exclusivement le salon du bulletin quotidien. Pour désactiver les salutations, mettre `"enabled": false`, puis redémarrer le service.

Activer **Message Content Intent** dans le [portail développeur Discord](https://discord.com/developers/applications), rubrique **Bot → Privileged Gateway Intents**, avant de lancer cette version. Sans cette activation, Discord refusera la connexion tant que `greetings.enabled` vaut `true`. Le message de démarrage signale le réglage à corriger. Voir la [documentation des intents](https://discordpy.readthedocs.io/en/stable/intents.html#privileged-intents).

Une réservation est enregistrée avant l'envoi pour éviter les doubles réponses simultanées ou après une coupure. Si Discord refuse explicitement la réponse (message supprimé ou permissions manquantes), la réservation est libérée. Si la réponse réseau est incertaine, le bot s'abstient de resaluer cette personne ce jour-là pour éviter un doublon. Les autres membres et le lendemain ne sont pas bloqués.

## Réponses aux pings du bot

Une mention directe (`@Bot du jour`, sélectionnée dans Discord) déclenche une réplique aléatoire parmi 32 phrases absurdes, par exemple :

> **Alex**, tu m'as invoqué pendant que j'apprenais le moonwalk à une courgette. Elle a déjà plus de rythme que mon processeur. 🥒🕺

Les réponses aux pings fonctionnent à toute heure, indépendamment de la limite quotidienne des salutations et même si celles-ci sont désactivées. Le bot ignore les autres bots, les webhooks, les messages privés, les autres serveurs, les mentions de rôles, `@everyone` et les notifications implicites d'une réponse sans mention écrite. Si un message contient une salutation et un ping, seule la réplique au ping est envoyée. Le bot cite le pseudo sans notifier le membre.

Par défaut, chaque personne peut obtenir **une réponse toutes les 30 secondes**, tous salons confondus. Ce délai persiste après redémarrage et utilise le temps écoulé réel, y compris pendant un changement d'heure. Les textes et pseudos reçus ne sont pas enregistrés. Une erreur réseau incertaine conserve le délai ; un refus explicite de Discord le libère.

Les anciennes configurations activent aussi cette fonction. Pour la régler, ajouter ce bloc dans `config.json` :

```json
"mentions": {
  "enabled": true,
  "channel_ids": [],
  "cooldown_seconds": 30
}
```

Une liste vide autorise tous les salons accessibles du serveur configuré ; sinon, indiquer leurs identifiants, indépendamment de `greetings.channel_ids`. `enabled: false` désactive les réponses aux pings. Le délai accepte de 1 à 3 600 secondes. Redémarrer le service après modification. Les pings seuls ne demandent pas Message Content Intent ; cet intent reste nécessaire si les salutations sont activées. Les répliques sont personnalisables dans `bonjour/mentions.py`.

## Relances d'un salon inactif

Le salon surveillé est celui du bulletin quotidien (`channel_id`). Par défaut, le bot attend **deux heures sans message humain**, puis publie un message aléatoire. Si personne ne parle, il en publie un nouveau **deux heures après le précédent**, entre **09:00 inclus et 22:00 exclu**, heure de Paris. Les nouveaux messages humains (y compris photos ou pièces jointes sans texte) remettent le délai de deux heures à zéro. Les autres salons, les modifications de messages, les réactions, les bots et les webhooks ne réinitialisent pas ce délai.

Les relances mélangent des phrases adaptées au matin, à midi, à l'après-midi ou à la soirée, huit blagues légères, huit phrases d'humour noir, quatre petits ASCII et quatre messages binaires. Les créneaux sont les mêmes que pour les salutations, à l'heure de Paris. Les blagues, ASCII et binaires sont précédés du contexte (« Pause de midi », par exemple). L'humour noir est macabre et absurde, par exemple « C'est tellement calme ici que même les fantômes ont demandé du télétravail ». Les binaires portent la mention « À décrypter », avec un encodage ASCII de huit bits par caractère. Le même message ne sort pas deux fois de suite, même après un redémarrage. Les banques de textes se trouvent dans `bonjour/inactivity.py`.

Si des membres sont en vocal au moment de l'envoi, la relance se termine aussi par une invitation, par exemple :

> 🎙️ Vous pouvez aussi venir discuter en vocal !
> • Rejoignez **Alex** et **Emma** dans **🔊 Général** !

Le nom du salon est une mention cliquable dans Discord. Les pseudos sont ceux affichés sur le serveur, sans notification. Plusieurs salons peuvent être proposés. Les bots, les salons vides, le salon AFK, les salons complets et les salons à accès restreint sont ignorés. Le bot propose uniquement les vocaux visibles et accessibles à `@everyone`, qu'il peut lui-même voir, sans refus explicite de visibilité ou de connexion pour un rôle ou un membre. Ce filtrage est volontairement prudent. L'affichage est limité à cinq salons et cinq pseudos par salon, avec le nombre de membres supplémentaires, dans la limite des 2 000 caractères de Discord.

Les présences sont consultées à chaque relance. S'il n'y a aucun vocal à proposer, seule la relance habituelle est publiée. Les annonces d'arrivée décrites plus bas fonctionnent en parallèle. Les pseudos et les présences vocales ne sont pas enregistrés dans SQLite. Le bot demande automatiquement l'intent standard `voice_states` ; aucune activation supplémentaire dans **Privileged Gateway Intents**, aucune permission de connexion au vocal et aucun intent des membres ou des présences ne sont nécessaires. Il ne rejoint pas les appels.

Pour modifier ces réglages, ajouter le bloc suivant à la configuration, en conservant les autres paramètres :

```json
"inactivity": {
  "enabled": true,
  "after_minutes": 120,
  "start": "09:00",
  "end": "22:00",
  "tone": "mixed",
  "include_voice": true
}
```

`tone` accepte `light`, `dark` ou `mixed` pour la sélection des blagues. Les ASCII et les binaires restent disponibles avec les trois tons. `enabled: false` désactive les relances. La plage horaire reste dans une même journée, entre 04:00 et 23:00 ; le délai accepte de 1 à 10 080 minutes. Une configuration existante sans ce bloc utilise les valeurs ci-dessus.

`include_voice: false` désactive uniquement l'invitation vocale dans les relances. L'invitation est activée par défaut, y compris avec une ancienne configuration sans ce paramètre. La réception des présences vocales reste active si les annonces d'arrivée sont activées. Redémarrer le bot après modification.

Au tout premier lancement sur un salon, le délai commence à la mise en route du suivi pour éviter une publication immédiate. Ensuite, les dates d'activité, de dernière relance et le dernier texte choisi sont conservés dans SQLite. Au redémarrage ou à la reconnexion, le bot vérifie les messages arrivés depuis sa dernière observation avant de relancer. Il consulte uniquement leurs métadonnées, sans enregistrer leur contenu ou le pseudo des membres. Le suivi d'inactivité seul ne nécessite pas Message Content Intent ; les réponses aux « bonjour » le demandent toujours.

Le contrôle a lieu toutes les 30 secondes. En dehors de la plage horaire, les relances attendent la prochaine ouverture ; aucune rafale ne rattrape les créneaux de nuit manqués. Le délai se calcule en temps écoulé réel (UTC), la plage d'envoi en heure de Paris, changements d'heure inclus.

Une réservation est enregistrée avant l'envoi pour éviter une relance immédiate en double après un arrêt ou une réponse réseau perdue. En cas de résultat réseau incertain, le bot attend un nouveau délai complet avant de réessayer. Si Discord refuse explicitement l'envoi, la réservation est annulée pour permettre une reprise après correction des permissions. Le serveur et le salon doivent rester accessibles avec **Voir le salon**, **Envoyer des messages** et **Voir les anciens messages**.

Après déploiement des fichiers modifiés sur le VPS, redémarrer depuis le compte administrateur `debian` : `sudo systemctl restart botdujour`. Les réponses quotidiennes aux « bonjour » gardent leur propre limite d'une fois par membre et par jour.

## Message de bonne nuit à 23 h 30

Chaque soir, vers **23:30, heure de Paris**, le bot publie une excuse absurde pour prendre congé dans le salon du bulletin (`channel_id`), parmi dix variantes :

> Bon bah, c'est pas l'tout, mais j'ai aquaponey sur la Lune. Le poney a déjà mis son scaphandre. Bonne nuit les humains ! 🐴🌕

Ce message fonctionne même si le salon est actif ou si les relances d'inactivité sont désactivées. Il ne déconnecte pas le bot : les réponses aux membres continuent. Les heures d'été et d'hiver sont gérées automatiquement. Le contrôle a lieu toutes les 30 secondes.

La fonction est active par défaut, y compris avec une ancienne configuration. Pour modifier l'heure ou la désactiver, ajouter dans `config.json` :

```json
"goodnight": {"enabled": true, "time": "23:30"}
```

`enabled: false` désactive ce message. L'heure accepte de 04:00 à 23:59, sans secondes ni fuseau. Les textes se personnalisent dans `bonjour/goodnight.py`. Après déploiement, redémarrer le service : `sudo systemctl restart botdujour`.

Une réservation SQLite limite l'envoi à une fois par jour, même après redémarrage. Si le bot se reconnecte entre l'heure prévue et minuit, il peut encore envoyer le message ; après minuit, aucun rattrapage de la veille n'a lieu. Un refus explicite de Discord autorise une nouvelle tentative. Une réponse réseau incertaine ou un arrêt après réservation conserve la réservation pour éviter un doublon ; le message peut alors manquer ce soir-là.

## Annonces d'arrivée en vocal

À chaque arrivée d'un membre dans un vocal public du serveur configuré, le bot publie immédiatement un message dans le salon du bulletin (`channel_id`), par exemple :

> 🎙️ **Alex** vient de rejoindre **🔊 Général** !
> Également en vocal : **Emma**.
> Venez discuter avec eux !

Le salon est cliquable et les pseudos ne déclenchent aucune notification. Si le membre est seul, le bot propose de lui tenir compagnie. Le message affiche jusqu'à cinq autres membres humains, puis leur nombre supplémentaire. Une arrivée dans un salon complet est annoncée, sans invitation à le rejoindre.

Ces annonces fonctionnent à toute heure, même pendant une discussion textuelle, avec les relances désactivées ou avec `inactivity.include_voice: false`. Chaque changement vers un autre vocal public est aussi annoncé. Les simples changements de micro, de casque ou de caméra et les départs ne provoquent aucun message. Les bots, les autres serveurs, les salons privés, les salons AFK et les salons de conférence sont ignorés. Le filtrage des accès est le même que pour les invitations des relances.

Les annonces sont actives par défaut, y compris dans une ancienne configuration. Pour les désactiver indépendamment des invitations dans les relances, ajouter :

```json
"voice": {"announce_joins": false}
```

Le bot ne réannonce pas les membres déjà présents au démarrage et ne rattrape pas les arrivées manquées pendant un arrêt. Une erreur d'envoi est journalisée, sans nouvel essai automatique pour éviter une annonce en double. Après transfert des fichiers sur le VPS, redémarrer le service : `sudo systemctl restart botdujour`.

## Configuration ultérieure

Modifier `config.json` avec `bot`, puis exécuter `systemctl restart botdujour` avec root (ou `sudo systemctl restart botdujour` avec un autre compte administrateur). Le bot contrôle que le salon appartient au serveur configuré. Un changement de salon s'applique au bulletin encore en attente ; un bulletin déjà envoyé n'est pas republié. Si la fenêtre est modifiée, l'heure conservée reste utilisée si elle appartient à la nouvelle fenêtre, sinon une nouvelle heure est tirée au sort. Ne pas déplacer la base de données lors d'un simple changement de salon.

Les fenêtres doivent rester dans la même journée entre 04:00 et 23:00 pour éviter les heures locales ambiguës des changements d'heure. Avec les valeurs par défaut, aucun rattrapage n'a lieu après 09:00. Si le bot redémarre avant 09:00 alors que l'heure choisie est passée, il tente l'envoi dans la fenêtre restante.

`calendar.json` permet d'ajouter des événements avec `title`, `text` et `source` (URL ou liste d'URL, conservée dans le fichier). Le texte accepte le gras `**...**` et les sauts de ligne pour présenter plusieurs journées :

- `dates` : clé `AAAA-MM-JJ`, pour un événement d'une année précise ou à date mobile ;
- `annual` : clé `MM-JJ`, seulement pour les événements annuels à date fixe ;
- `months` : numéro du mois sous forme de texte, pour un thème mensuel rappelé le lundi.

La priorité est : date précise personnalisée, événement annuel personnalisé, calendrier ONU, thème mensuel le lundi, puis petit mot de saison. Un texte personnalisé remplace la rubrique ONU entière de cette date ; il peut donc décrire plusieurs événements. Une journée complémentaire qui ne se tient que certaines années doit figurer dans `dates`, pas dans `annual`. Après modification, essayer `--preview --date AAAA-MM-JJ` ; le bot refuse les messages dépassant la limite Discord de 2 000 caractères. Les horaires du soleil restent calculés pour les coordonnées configurées, même si la ville n'est plus affichée dans le bulletin.

Le bulletin ne télécharge pas le site de l'ONU chaque matin : il lit `un_calendar.json`. Les semaines internationales sont annoncées à leur ouverture uniquement. Les dates lunaires sans règle annuelle fiable, comme le Vesak, sont enregistrées pour la seule année confirmée ; elles doivent être actualisées pour les années suivantes.

Pour actualiser la copie locale (aucun envoi Discord) :

```bash
python scripts/update_un_calendar.py
```

On peut aussi importer une page HTML enregistrée avec `--html chemin/vers/page.html`. Relire le diff, notamment les nouvelles dates mobiles ou périodiques, puis lancer les tests et redémarrer le bot. L'import applique les règles révisées des événements mobiles connus et corrige certaines annotations périmées de la liste à partir des pages des organismes responsables ; les liens correspondants sont conservés dans le fichier. Une page incomplète ou de structure inconnue est refusée avant d'écraser le calendrier.

## Redémarrages et doublons

Conserver la base SQLite et lancer une seule instance. Un verrou système évite deux processus sur la même base. La date locale et l'état d'envoi sont persistés par serveur. Avant de publier, le bot recherche ses propres bulletins du jour dans l'historique du salon grâce à leur ligne de date, indépendamment des réponses aux nouveaux « bonjour ». Les anciens messages avec une dernière ligne `Bulletin du AAAA-MM-JJ` restent reconnus. Le nouveau bulletin n'affiche plus ce pied technique.

Si un arrêt survient après l'envoi et avant l'enregistrement local, l'historique permet normalement de retrouver le message. Si l'issue d'un envoi réseau reste incertaine et qu'aucun message n'est retrouvé, le jour est marqué `uncertain` et le bot s'abstient de renvoyer automatiquement. Dans ce cas rare, vérifier le salon et les journaux ; le bulletin peut manquer pour cette journée. Ne pas effacer la base pour forcer une nouvelle tentative. Les jours suivants continuent normalement.

Un aperçu local en ligne utilise le même verrou que le service : l'exécuter avant le démarrage du service ou utiliser `/bonjour-apercu` lorsqu'il fonctionne. L'aperçu `--offline` n'utilise pas la base.

## Développement et vérification

Python 3.12 minimum pour cette base ; Debian 13 fournit une version compatible. Dans le dossier du projet :

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python bot.py --config config.example.json --preview --offline --date 2026-10-19
```

Sous Windows, utiliser `.venv\Scripts\python.exe`. Les tests ne se connectent pas à Discord et n'envoient aucun message. Ils couvrent notamment les deux changements d'heure, les redémarrages, la reprise après un envoi interrompu, les erreurs réseau et le rendu d'une année bissextile.

Sources techniques : [discord.py](https://discordpy.readthedocs.io/en/stable/), [Astral](https://astral.readthedocs.io/en/latest/), [Nominis](https://nominis.cef.fr/contenus/integrations.html). Les dates internationales sont fondées sur le [calendrier des Nations unies](https://www.un.org/observances/list-days-weeks).
#   b o t d u j o u r  
 
