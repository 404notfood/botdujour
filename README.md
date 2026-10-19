# Bot du jour — Discord

Bot Python pour Debian 13 : un bulletin en français dans **un serveur et un salon configurés**, chaque matin entre **08:00 et 09:00, heure de Paris**. L'heure est tirée au sort chaque jour, à la minute, puis conservée dans SQLite. La vérification a lieu toutes les 30 secondes : l'envoi peut donc suivre la minute choisie de quelques secondes.

`Europe/Paris` gère les heures d'été et d'hiver, indépendamment du fuseau du VPS. Ne pas remplacer ce fuseau par un décalage fixe UTC+1 ou UTC+2.

## Contenu

- Date française, soleil et durée du jour calculés localement avec Astral.
- **Paris sert de référence pour le soleil.** Il n'existe pas un seul horaire valable pour toute la France métropolitaine. La ville et ses coordonnées sont modifiables.
- Prénoms du jour via l'[API officielle Nominis](https://nominis.cef.fr/contenus/integrations.html), avec cache par date et lien de crédit dans le message. Ce calendrier peut différer du calendrier des fleuristes. Le bot utilise les prénoms principaux renvoyés, au maximum six. En cas de panne et sans cache, il affiche que les prénoms sont indisponibles.
- Quelques journées annuelles et Octobre rose sont inclus dans `calendar.json`. **Ce calendrier de journées particulières n'est pas exhaustif** ; les sources y sont indiquées. Sans événement renseigné, la rubrique est omise. Les textes sont rédigés pour ce bot.
- Une formule de bonne journée adaptée au jour de la semaine, parmi deux variantes par jour, choisie de façon stable pour une date donnée.
- Aucun service d'IA, aucune clé d'API payante, aucun accès au contenu des messages des membres nécessaire.

## 1. Créer l'application Discord

1. Ouvrir le [portail développeur Discord](https://discord.com/developers/applications), créer une application puis son bot.
2. Dans la page **Bot**, récupérer le token et le conserver uniquement dans `.env`. Ne pas le publier ou l'envoyer dans un chat. Si le token a été divulgué, le réinitialiser.
3. Dans **OAuth2 → URL Generator**, choisir `bot` et `applications.commands`.
4. Accorder uniquement **Voir le salon**, **Envoyer des messages** et **Voir les anciens messages**. Pas besoin de la permission Administrateur ni d'intent privilégié.
5. Utiliser le lien d'invitation pour ajouter le bot au serveur voulu. Vérifier également les permissions spécifiques du salon.
6. Dans Discord, activer **Paramètres utilisateur → Avancés → Mode développeur**. Clic droit sur le serveur → **Copier l'identifiant du serveur**, puis sur le salon → **Copier l'identifiant du salon**.

Le salon doit être un salon textuel classique ou d'annonces, pas un fil, un forum, une catégorie ou un message privé.

## 2. Installation Debian 13

Les commandes suivantes s'exécutent sur le VPS avec un compte ayant accès à `sudo`. Copier d'abord ce projet dans `/opt/botdujour` (SFTP ou `scp`), sans transférer `.venv`, `__pycache__`, les dossiers temporaires ni les données locales.

```bash
sudo apt update
sudo apt install -y python3 python3-venv tzdata ca-certificates
sudo useradd --system --user-group --home-dir /opt/botdujour --shell /usr/sbin/nologin botdujour
sudo install -d -o botdujour -g botdujour -m 750 /var/lib/botdujour
cd /opt/botdujour
sudo python3 -m venv .venv
sudo .venv/bin/python -m pip install -r requirements.txt
sudo cp config.example.json config.json
sudo cp .env.example .env
sudo nano config.json
sudo nano .env
```

Si le compte système `botdujour` existe déjà, ne pas répéter `useradd`.

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
sudo chown root:botdujour /opt/botdujour/.env /opt/botdujour/config.json
sudo chmod 640 /opt/botdujour/.env /opt/botdujour/config.json
sudo -u botdujour .venv/bin/python bot.py --check
sudo -u botdujour .venv/bin/python bot.py --preview --date 2026-10-19
```

`--check` valide les fichiers et le rendu du jour sans se connecter à Discord. L'aperçu appelle Nominis, écrit son cache dans la base et affiche le message dans le terminal ; il ne publie rien sur Discord. Pour un aperçu sans réseau, ajouter `--offline` (les prénoms seront indiqués comme indisponibles).

## 3. Démarrage automatique

```bash
sudo cp deploy/botdujour.service /etc/systemd/system/botdujour.service
sudo systemctl daemon-reload
sudo systemctl enable --now botdujour
sudo systemctl status botdujour
sudo journalctl -u botdujour -f
```

Le service démarre avec le VPS et redémarre après un échec. Les journaux signalent la connexion, les permissions, l'heure choisie en heure de Paris et les envois. Le préfixe des journaux suit éventuellement le fuseau du système ; l'heure annoncée pour le bulletin est toujours celle de Paris. Il suffit de connexions sortantes HTTPS et WebSocket vers Discord, et HTTPS vers Nominis ; aucun port entrant n'est nécessaire.

La commande Discord **`/bonjour-apercu`** affiche le bulletin uniquement à son auteur. Elle exige la permission **Gérer le serveur**, vérifiée également à l'exécution. Aucun bouton ni commande ne provoque un envoi public de test.

## Configuration ultérieure

Modifier `config.json`, puis `sudo systemctl restart botdujour`. Le bot contrôle que le salon appartient au serveur configuré. Un changement de salon s'applique au bulletin encore en attente ; un bulletin déjà envoyé n'est pas republié. Si la fenêtre est modifiée, l'heure conservée reste utilisée si elle appartient à la nouvelle fenêtre, sinon une nouvelle heure est tirée au sort. Ne pas déplacer la base de données lors d'un simple changement de salon.

Les fenêtres doivent rester dans la même journée entre 04:00 et 23:00 pour éviter les heures locales ambiguës des changements d'heure. Avec les valeurs par défaut, aucun rattrapage n'a lieu après 09:00. Si le bot redémarre avant 09:00 alors que l'heure choisie est passée, il tente l'envoi dans la fenêtre restante.

`calendar.json` permet d'ajouter des événements avec `title`, `text` et `source` :

- `dates` : clé `AAAA-MM-JJ`, pour un événement d'une année précise ou à date mobile ;
- `annual` : clé `MM-JJ`, seulement pour les événements annuels à date fixe ;
- `months` : numéro du mois sous forme de texte, pour un thème mensuel de repli.

La priorité est : date précise, événement annuel, thème mensuel. Une journée mondiale qui ne se tient que certaines années doit figurer dans `dates`, pas dans `annual`. Après modification, essayer `--preview --date AAAA-MM-JJ` ; le bot refuse les messages dépassant la limite Discord de 2 000 caractères.

## Redémarrages et doublons

Conserver la base SQLite et lancer une seule instance. Un verrou système évite deux processus sur la même base. La date locale et l'état d'envoi sont persistés par serveur. Avant de publier, le bot recherche ses propres bulletins du jour dans l'historique du salon. Il n'analyse pas les messages des membres. Ne pas retirer la dernière ligne `Bulletin du AAAA-MM-JJ` des messages du bot.

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