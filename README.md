# Bot du jour — Discord

Bot Python pour Debian 13 : un bulletin en français dans **un serveur et un salon configurés**, chaque matin entre **08:00 et 09:00, heure de Paris**. L'heure est tirée au sort chaque jour, à la minute, puis conservée dans SQLite. La vérification a lieu toutes les 30 secondes : l'envoi peut donc suivre la minute choisie de quelques secondes.

`Europe/Paris` gère les heures d'été et d'hiver, indépendamment du fuseau du VPS. Ne pas remplacer ce fuseau par un décalage fixe UTC+1 ou UTC+2.

## Contenu

- Date française, soleil et durée du jour calculés localement avec Astral.
- **Paris sert de référence pour le soleil.** Il n'existe pas un seul horaire valable pour toute la France métropolitaine. La ville et ses coordonnées sont modifiables.
- Prénoms du jour via l'[API officielle Nominis](https://nominis.cef.fr/contenus/integrations.html), avec cache par date et lien de crédit dans le message. Ce calendrier peut différer du calendrier des fleuristes. Le bot utilise les prénoms principaux renvoyés, au maximum six. En cas de panne et sans cache, il affiche que les prénoms sont indisponibles.
- Quelques journées annuelles et Octobre rose sont inclus dans `calendar.json`. **Ce calendrier de journées particulières n'est pas exhaustif** ; les sources y sont indiquées. Sans événement renseigné, la rubrique est omise. Les textes sont rédigés pour ce bot.
- Une formule de bonne journée adaptée au jour de la semaine, parmi deux variantes par jour, choisie de façon stable pour une date donnée.
- Réponse à un message commençant par « bonjour », avec le pseudo du membre sur le serveur et une phrase polie et humoristique. Une seule réponse par membre et par jour, tous salons confondus, selon la date de Paris ; le suivi persiste après redémarrage.
- Relances du salon du bulletin après deux heures sans message humain, puis toutes les deux heures si le silence continue : humour léger ou noir, petit ASCII ou message binaire à décrypter. Envois entre 09:00 et 22:00, heure de Paris.
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

Le projet est installé dans `/home/bot/app/botdujour` et le service fonctionne avec l'utilisateur existant `bot`, qui n'a pas besoin de sudo. Utiliser une session `root` (ou un autre compte administrateur avec sudo) uniquement pour les paquets système et le service. `su -` permet de passer de `bot` à `root` si le mot de passe root est disponible ; sinon ouvrir une connexion administrateur séparée. Ne pas transférer un environnement `.venv` Windows sur Debian : le créer sur le VPS.

Avec **root**, préparer les dépendances système et le dossier de données :

```bash
apt update
apt install -y python3 python3-venv tzdata ca-certificates
install -d -o bot -g bot -m 750 /var/lib/botdujour
```

Avec **bot**, installer les bibliothèques Python et remplir la configuration. Depuis une session root, utiliser `su - bot` pour ouvrir cette session :

```bash
cd /home/bot/app/botdujour
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp -n config.example.json config.json
cp -n .env.example .env
nano config.json
nano .env
```

Les copies avec `cp -n` préservent une configuration déjà renseignée.

Dans `config.json`, mettre les vrais identifiants **entre guillemets** et utiliser `/var/lib/botdujour/bot.sqlite3` pour `state_db` afin de respecter les droits du service Debian :

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

Avec **root**, installer et démarrer le service. Si la session `bot` a été ouverte avec `su - bot`, utiliser `exit` pour revenir à root :

```bash
cp /home/bot/app/botdujour/deploy/botdujour.service /etc/systemd/system/botdujour.service
systemctl daemon-reload
systemctl enable --now botdujour
systemctl status botdujour
journalctl -u botdujour -f
```

Le service utilise `User=bot`, `WorkingDirectory=/home/bot/app/botdujour` et `ProtectHome=read-only` afin de pouvoir lire le projet situé dans `/home`. La base reste dans `/var/lib/botdujour`, seul emplacement persistant ouvert en écriture par le service. Ne pas réutiliser l'ancien service pointant vers `/opt/botdujour` ou avec `ProtectHome=true`.

Le service démarre avec le VPS et redémarre après un échec. Les journaux signalent la connexion, les permissions, l'heure choisie en heure de Paris et les envois. Le préfixe des journaux suit éventuellement le fuseau du système ; l'heure annoncée pour le bulletin est toujours celle de Paris. Il suffit de connexions sortantes HTTPS et WebSocket vers Discord, et HTTPS vers Nominis ; aucun port entrant n'est nécessaire.

La commande Discord **`/bonjour-apercu`** affiche le bulletin uniquement à son auteur. Elle exige la permission **Gérer le serveur**, vérifiée également à l'exécution. Aucun bouton ni commande ne provoque un envoi public de test.

## Réponses aux bonjour

Un membre qui écrit « Bonjour », « Bonjour à tous ! » ou « 👋 Bonjour » reçoit une réponse dans le même salon, par exemple :

> Salut **Alex** ! Comment vas-tu ? Ça va coder aujourd'hui, ou le café réclame encore une mise à jour ? ☕😄

Le bot utilise le pseudo affiché sur le serveur (`display_name`), sans notification de mention. Il ignore les autres bots, les webhooks, les messages privés, les autres serveurs et un « bonjour » simplement cité au milieu d'un message. Il ne répond pas non plus aux modifications de messages.

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

## Relances d'un salon inactif

Le salon surveillé est celui du bulletin quotidien (`channel_id`). Par défaut, le bot attend **deux heures sans message humain**, puis publie un message aléatoire. Si personne ne parle, il en publie un nouveau **deux heures après le précédent**, entre **09:00 inclus et 22:00 exclu**, heure de Paris. Les nouveaux messages humains (y compris photos ou pièces jointes sans texte) remettent le délai de deux heures à zéro. Les autres salons, les modifications de messages, les réactions, les bots et les webhooks ne réinitialisent pas ce délai.

Les relances mélangent huit blagues légères, huit phrases d'humour noir, quatre petits ASCII et quatre messages binaires. L'humour noir est macabre et absurde, par exemple « C'est tellement calme ici que même les fantômes ont demandé du télétravail ». Les binaires portent la mention « À décrypter », avec un encodage ASCII de huit bits par caractère. Le même message ne sort pas deux fois de suite, même après un redémarrage. Les banques de textes se trouvent dans `bonjour/inactivity.py`.

Pour modifier ces réglages, ajouter le bloc suivant à la configuration, en conservant les autres paramètres :

```json
"inactivity": {
  "enabled": true,
  "after_minutes": 120,
  "start": "09:00",
  "end": "22:00",
  "tone": "mixed"
}
```

`tone` accepte `light`, `dark` ou `mixed` pour la sélection des blagues. Les ASCII et les binaires restent disponibles avec les trois tons. `enabled: false` désactive les relances. La plage horaire reste dans une même journée, entre 04:00 et 23:00 ; le délai accepte de 1 à 10 080 minutes. Une configuration existante sans ce bloc utilise les valeurs ci-dessus.

Au tout premier lancement sur un salon, le délai commence à la mise en route du suivi pour éviter une publication immédiate. Ensuite, les dates d'activité, de dernière relance et le dernier texte choisi sont conservés dans SQLite. Au redémarrage ou à la reconnexion, le bot vérifie les messages arrivés depuis sa dernière observation avant de relancer. Il consulte uniquement leurs métadonnées, sans enregistrer leur contenu ou le pseudo des membres. Le suivi d'inactivité seul ne nécessite pas Message Content Intent ; les réponses aux « bonjour » le demandent toujours.

Le contrôle a lieu toutes les 30 secondes. En dehors de la plage horaire, les relances attendent la prochaine ouverture ; aucune rafale ne rattrape les créneaux de nuit manqués. Le délai se calcule en temps écoulé réel (UTC), la plage d'envoi en heure de Paris, changements d'heure inclus.

Une réservation est enregistrée avant l'envoi pour éviter une relance immédiate en double après un arrêt ou une réponse réseau perdue. En cas de résultat réseau incertain, le bot attend un nouveau délai complet avant de réessayer. Si Discord refuse explicitement l'envoi, la réservation est annulée pour permettre une reprise après correction des permissions. Le serveur et le salon doivent rester accessibles avec **Voir le salon**, **Envoyer des messages** et **Voir les anciens messages**.

Après déploiement des fichiers modifiés sur le VPS, redémarrer depuis le compte administrateur `debian` : `sudo systemctl restart botdujour`. Les réponses quotidiennes aux « bonjour » gardent leur propre limite d'une fois par membre et par jour.

## Configuration ultérieure

Modifier `config.json` avec `bot`, puis exécuter `systemctl restart botdujour` avec root (ou `sudo systemctl restart botdujour` avec un autre compte administrateur). Le bot contrôle que le salon appartient au serveur configuré. Un changement de salon s'applique au bulletin encore en attente ; un bulletin déjà envoyé n'est pas republié. Si la fenêtre est modifiée, l'heure conservée reste utilisée si elle appartient à la nouvelle fenêtre, sinon une nouvelle heure est tirée au sort. Ne pas déplacer la base de données lors d'un simple changement de salon.

Les fenêtres doivent rester dans la même journée entre 04:00 et 23:00 pour éviter les heures locales ambiguës des changements d'heure. Avec les valeurs par défaut, aucun rattrapage n'a lieu après 09:00. Si le bot redémarre avant 09:00 alors que l'heure choisie est passée, il tente l'envoi dans la fenêtre restante.

`calendar.json` permet d'ajouter des événements avec `title`, `text` et `source` :

- `dates` : clé `AAAA-MM-JJ`, pour un événement d'une année précise ou à date mobile ;
- `annual` : clé `MM-JJ`, seulement pour les événements annuels à date fixe ;
- `months` : numéro du mois sous forme de texte, pour un thème mensuel de repli.

La priorité est : date précise, événement annuel, thème mensuel. Une journée mondiale qui ne se tient que certaines années doit figurer dans `dates`, pas dans `annual`. Après modification, essayer `--preview --date AAAA-MM-JJ` ; le bot refuse les messages dépassant la limite Discord de 2 000 caractères.

## Redémarrages et doublons

Conserver la base SQLite et lancer une seule instance. Un verrou système évite deux processus sur la même base. La date locale et l'état d'envoi sont persistés par serveur. Avant de publier, le bot recherche ses propres bulletins du jour dans l'historique du salon, indépendamment des réponses aux nouveaux « bonjour ». Ne pas retirer la dernière ligne `Bulletin du AAAA-MM-JJ` des messages du bot.

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
