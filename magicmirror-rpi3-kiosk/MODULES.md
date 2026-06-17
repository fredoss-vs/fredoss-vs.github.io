# MODULES.md — MagicMirror² Configuration Globale

Documentation de référence de tous les modules configurés sur le Raspberry Pi 3B + écran DSI OSOYOO 5" (800×480).

---

<details>
<summary><strong>🏗️ Infrastructure — Services systèmes</strong></summary>

## Infrastructure

Deux services systemd supplémentaires au-delà de MagicMirror et Kiosk (voir `README.md`).

### ics-server

Serveur HTTP Node.js minimal qui expose les fichiers `.ics` locaux sur le port **8090**, consommés par le module `calendar`.

```ini
# /etc/systemd/system/ics-server.service
[Unit]
Description=ICS Static File Server
After=network.target

[Service]
Type=simple
User=toto
WorkingDirectory=/home/toto/ics
ExecStart=/home/toto/.nvm/versions/node/v26.3.0/bin/node -e "\
  require('http').createServer((req,res)=>{\
    const fs=require('fs');\
    const f='/home/toto/ics'+req.url;\
    fs.readFile(f,(e,d)=>{\
      if(e){res.writeHead(404);res.end()}\
      else{res.writeHead(200,{'Content-Type':'text/calendar'});res.end(d)}\
    })\
  }).listen(8090)"
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable ics-server
sudo systemctl start ics-server

# Vérification
curl -s http://localhost:8090/valais.ics | head -3
```

### Proxy CORS

Activé dans `config.js` pour permettre aux modules d'accéder à des ressources externes :

```js
cors: "allowAll",
```

> **Note :** Pour les URLs `localhost`, le proxy CORS n'est **pas** nécessaire — le module `calendar` accède au fichier côté serveur Node.js directement.

</details>

---

<details>
<summary><strong>🕐 Horloge — module clock</strong></summary>

## Clock

Affiche l'heure et la date en haut à gauche.

```js
{
    module: "clock",
    position: "top_left",
    config: {
        displaySeconds: false,
        showDate: true,
    }
},
```

| Paramètre | Valeur | Description |
|---|---|---|
| `position` | `top_left` | Zone d'affichage |
| `displaySeconds` | `false` | Secondes masquées — gain de place |
| `showDate` | `true` | Affiche la date complète |

</details>

---

<details>
<summary><strong>📅 Calendrier — Jours fériés Valais</strong></summary>

## Calendar — Jours fériés Valais

Affiche les 2 prochains jours fériés du canton du Valais.

### Fichier iCal

Les jours fériés sont stockés dans un fichier statique local mis à jour annuellement.

```bash
# Emplacement
~/ics/valais.ics
```

Les 11 jours fériés valaisans 2026 :

| Date | Jour férié |
|---|---|
| 01.01 | Nouvel An |
| 19.03 | Saint-Joseph |
| 03.04 | Vendredi Saint |
| 06.04 | Lundi de Pâques |
| 14.05 | Ascension |
| 04.06 | Fête-Dieu |
| 01.08 | Fête Nationale |
| 15.08 | Assomption |
| 01.11 | Toussaint |
| 08.12 | Immaculée Conception |
| 25.12 | Noël |

### Configuration config.js

```js
{
    module: "calendar",
    header: "Prochains jours fériés",
    position: "top_left",
    config: {
        colored: true,
        maximumEntries: 2,
        maximumNumberOfDays: 365,
        fetchInterval: 24 * 60 * 60 * 1000,
        calendars: [
            {
                symbol: "church",
                color: "#e74c3c",
                url: "http://localhost:8090/valais.ics"
            }
        ]
    }
},
```

| Paramètre | Valeur | Description |
|---|---|---|
| `maximumEntries` | `2` | 2 prochains jours fériés uniquement |
| `maximumNumberOfDays` | `365` | Fenêtre de recherche sur 1 an |
| `url` | `http://localhost:8090/valais.ics` | Servi par ics-server, pas de proxy CORS nécessaire |
| `fetchInterval` | `86400000` | Rechargement toutes les 24h |

### Mise à jour annuelle

```bash
nano ~/ics/valais.ics
# Dupliquer les blocs VEVENT en incrémentant l'année

sudo systemctl restart ics-server
```

</details>

---

<details>
<summary><strong>🌤️ Météo — Savièse (actuelle + prévisions 2 jours)</strong></summary>

## Weather — Savièse

Deux instances du module `weather` : météo actuelle et prévisions sur 2 jours.
Provider : **openmeteo** (gratuit, sans clé API).
Coordonnées : **Savièse, Valais** (46.2333° N, 7.3667° E).

### Météo actuelle

```js
{
    module: "weather",
    header: "Savièse — Maintenant",
    position: "top_right",
    config: {
        weatherProvider: "openmeteo",
        type: "current",
        lat: 46.2333,
        lon: 7.3667,
        showWindDirection: false,
        showWindDirectionAsArrow: false,
        showHumidity: true,
    }
},
```

### Prévisions 2 jours

```js
{
    module: "weather",
    header: "Savièse — 2 jours",
    position: "top_right",
    config: {
        weatherProvider: "openmeteo",
        type: "forecast",
        lat: 46.2333,
        lon: 7.3667,
        maxNumberOfDays: 2,
        showWindDirection: false,
        colored: true,
    }
},
```

| Paramètre | Valeur | Description |
|---|---|---|
| `weatherProvider` | `openmeteo` | Gratuit, sans clé API |
| `lat` / `lon` | `46.2333` / `7.3667` | Coordonnées Savièse |
| `maxNumberOfDays` | `2` | **Paramètre correct** pour openmeteo (pas `maximumNumberOfDays`) |
| `showWindDirection` | `false` | Masqué — gain de place sur 800×480 |
| `colored` | `true` | Icônes météo en couleur |

> **Point critique :** Le paramètre limitant les jours de prévision avec openmeteo est `maxNumberOfDays` et non `maximumNumberOfDays`. Un reboot complet est nécessaire après modification pour que le changement soit pris en compte par Chromium.

</details>

---

<details>
<summary><strong>📰 Actualités — Newsfeed Suisse</strong></summary>

## Newsfeed — Actualités Suisse

Fil d'actualités Google News en français, affiché en bas de l'écran.

```js
{
    module: "newsfeed",
    position: "bottom_bar",
    config: {
        feeds: [
            {
                title: "Suisse",
                url: "https://news.google.com/rss?hl=fr&gl=CH&ceid=CH:fr"
            }
        ],
        showSourceTitle: true,
        showPublishDate: false,
        broadcastNewsFeeds: true,
        broadcastNewsUpdates: true,
        updateInterval: 10000,
    }
},
```

| Paramètre | Valeur | Description |
|---|---|---|
| `position` | `bottom_bar` | Collé en bas de l'écran |
| `showPublishDate` | `false` | Masqué — gain de place |
| `updateInterval` | `10000` | Rotation toutes les 10 secondes |

### Alignement CSS

Le newsfeed est aligné à gauche via `config/custom.css` :

```css
/* /home/toto/MagicMirror/config/custom.css */
.region.bottom.bar {
    width: 100%;
    text-align: left;
}

.region.bottom.bar .module {
    font-size: 14px;
    opacity: 0.75;
}
```

> **Point critique :** Le fichier custom CSS doit être placé dans `config/custom.css` et non `css/custom.css` — MagicMirror le charge via `loader.js` depuis le chemin `config/custom.css`.

</details>

---

<details>
<summary><strong>⏱️ Minuteur — MMM-Timer (module non officiel)</strong></summary>

## MMM-Timer

> Module développé spécifiquement pour ce projet. Non publié sur le catalogue officiel.

Compte à rebours plein écran avec verrouillage de page et alerte visuelle clignotante à la fin du décompte.

### Fonctionnalités

- Affichage `HH:MM:SS` centré en plein écran
- États : **IDLE** → **RUNNING** → **PAUSED** → **FINISHED**
- Verrouillage de la navigation MMM-pages pendant l'exécution
- Clignotement rouge continu à `00:00:00`, bouton STOP pour réinitialiser
- Compatible écran tactile

### Configuration config.js

```js
{
    module: "MMM-Timer",
    position: "fullscreen_above",
    config: {
        defaultHours: 0,
        defaultMinutes: 15,
        defaultSeconds: 0,
        showControls: true,
        timerFontSize: "8rem",
        flashColor: "#ff0000",
        flashInterval: 500,
        lockPageOnStart: true,
        targetPage: 5,          // index 0-based de la page MMM-pages
        restoreNavigationOnStop: true,
        autoResetAfterStop: true
    }
}
```

### Intégration MMM-pages

| Notification envoyée | Payload | Effet |
|---|---|---|
| `PAGE_SELECT` | index (0-based) | Bascule sur la page du timer |
| `PAUSE_ROTATION` | — | Verrouille la navigation |
| `RESUME_ROTATION` | — | Réactive la rotation des pages |

> Aucune dépendance externe. JavaScript natif uniquement. Validé avec MagicMirror² ≥ 2.33.

</details>

---

## Récapitulatif des positions

```
┌─────────────────────────────────────────────┐  800px
│  [top_left]          │  [top_right]          │
│  • clock             │  • weather current    │
│  • calendar (fériés) │  • weather forecast   │
│                      │                       │
│                                              │
│──────────────────────────────────────────────│
│  [bottom_bar]                                │  480px
│  • newsfeed (actualités suisse)              │
└─────────────────────────────────────────────┘
```

## Commandes utiles

```bash
# Redémarrer MagicMirror
sudo systemctl restart magicmirror

# Recharger l'affichage (obligatoire pour voir les changements)
pkill chromium && sudo systemctl restart kiosk

# Reboot complet (nécessaire pour certains changements de config météo)
sudo reboot

# Logs MagicMirror en temps réel
journalctl -u magicmirror -f

# Vérifier tous les services
sudo systemctl status magicmirror ics-server kiosk
```

## Arborescence des fichiers de configuration

```
/home/toto/
├── ics/
│   └── valais.ics                    ← Jours fériés Valais
└── MagicMirror/
    └── config/
        ├── config.js                 ← Configuration principale
        └── custom.css                ← Surcharge CSS (alignement newsfeed)

/etc/systemd/system/
├── magicmirror.service
├── ics-server.service
└── kiosk.service
```
