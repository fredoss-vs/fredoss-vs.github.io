# MagicMirror² — Raspberry Pi 3B + Écran DSI OSOYOO 5"

Configuration personnalisée de **[MagicMirror²](https://magicmirror.builders/)** — plateforme open-source de miroir connecté modulaire — déployée sur Raspberry Pi 3B avec écran tactile DSI OSOYOO 5" sous Wayland/Chromium kiosk.

> Ce dépôt contient la configuration, les modules utilisés et la documentation d'installation propres à ce setup.
> Le code source de MagicMirror² provient du [dépôt officiel](https://github.com/MagicMirrorOrg/MagicMirror) — voir [docs.magicmirror.builders](https://docs.magicmirror.builders/) et [modules.magicmirror.builders](https://modules.magicmirror.builders/) pour la référence complète.

---

## Sources

| Ressource | Lien |
|---|---|
| Site officiel | [magicmirror.builders](https://magicmirror.builders/) |
| Documentation | [docs.magicmirror.builders](https://docs.magicmirror.builders/) |
| Catalogue de modules | [modules.magicmirror.builders](https://modules.magicmirror.builders/) |
| Dépôt GitHub | [MagicMirrorOrg/MagicMirror](https://github.com/MagicMirrorOrg/MagicMirror) |
| Écran | [OSOYOO 5" DSI Touch Screen](https://osoyoo.com/2021/09/23/osoyoo-5-inch-hdmi-800-x-480-capacitive-touch-lcd-display/) |

### Modules tiers utilisés

| Module | Source |
|---|---|
| MMM-pages | [edward-shen/MMM-pages](https://github.com/edward-shen/MMM-pages) |
| MMM-page-indicator | [edward-shen/MMM-page-indicator](https://github.com/edward-shen/MMM-page-indicator) |
| MMM-MQTT | [ottopaulsen/MMM-MQTT](https://github.com/ottopaulsen/MMM-MQTT) |
| MMM-AVStock | [lavolp3/MMM-AVStock](https://github.com/lavolp3/MMM-AVStock) |
| MMM-NewsAPI | [hobbyquaker/MMM-NewsAPI](https://github.com/hobbyquaker/MMM-NewsAPI) |
| **MMM-Timer** | **Module non officiel — développé pour ce projet** |

> La configuration complète de chaque module est documentée dans [`MODULES.md`](MODULES.md).

---

## Matériel

| Composant | Modèle |
|---|---|
| SBC | Raspberry Pi 3B (ARMv8 / arm64) |
| Écran | OSOYOO 5" DSI Touch Screen (800×480, capacitif) |
| OS | Raspberry Pi OS Lite 64-bit — Debian Trixie (kernel 6.12.x) |

---

## Prérequis système

- Raspberry Pi OS Lite 64-bit flashé sur SD
- Accès SSH actif
- Connexion réseau fonctionnelle
- Utilisateur non-root avec sudo (exemple : `toto`)

---

## 1. Installation de Node.js via nvm

MagicMirror² v2.33+ requiert Node.js ≥ 22. L'installation via **nvm** est recommandée sur Raspberry Pi OS Lite — le paquet système `nodejs` est souvent trop ancien.

```bash
# Installer nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash

# Recharger le shell
source ~/.bashrc

# Installer Node.js 22 (LTS)
nvm install 22
nvm use 22
nvm alias default 22

# Vérifier
node --version   # doit afficher v22.x ou supérieur
which node       # doit afficher /home/<user>/.nvm/versions/node/v22.x.x/bin/node
```

> **Important :** Noter le chemin absolu retourné par `which node` — il sera nécessaire pour le service systemd (étape 7).

---

## 2. Installation de MagicMirror²

```bash
git clone https://github.com/MagicMirrorOrg/MagicMirror.git ~/MagicMirror
cd ~/MagicMirror
npm install husky
node --run install-mm
```

> **Note :** Le script `postinstall` installe puis retire automatiquement husky — c'est le comportement attendu. Le message `no husky installed` en fin d'exécution est normal.

---

## 3. Configuration de MagicMirror²

```bash
cp ~/MagicMirror/config/config.js.sample ~/MagicMirror/config/config.js
cp ~/MagicMirror/config/custom.css.sample ~/MagicMirror/css/custom.css
```

Éditer `config.js` pour autoriser les connexions réseau :

```bash
nano ~/MagicMirror/config/config.js
```

Modifier les lignes suivantes :

```js
address: "0.0.0.0",   // écoute sur toutes les interfaces (était "localhost")
ipWhitelist: [],       // autorise tous les clients (était ["127.0.0.1", ...])
```

Tester le serveur manuellement :

```bash
cd ~/MagicMirror
node --run server
# attendu : Ready to go! Please point your browser to: http://0.0.0.0:8080
```

Vérifier depuis un autre appareil sur le réseau : `http://<ip-du-pi>:8080`

---

## 4. Installation de Wayfire (compositeur Wayland)

Electron n'est pas supporté de façon fiable sur Pi 3B. L'affichage repose sur Wayfire (compositeur Wayland léger) + Chromium en mode kiosk.

```bash
sudo apt install --no-install-recommends wayfire chromium seatd -y
```

---

## 5. Configuration de seatd et des groupes utilisateur

```bash
sudo systemctl enable seatd
sudo systemctl start seatd

# Créer le groupe seat s'il n'existe pas
sudo groupadd seat 2>/dev/null || true

# Ajouter l'utilisateur aux groupes nécessaires
sudo usermod -aG video,input,render,seat $USER

# Activer le linger pour la session utilisateur persistante (requis par systemd sans session PAM)
sudo loginctl enable-linger $USER
```

> **Reboot obligatoire** pour que les groupes soient effectifs :
> ```bash
> sudo reboot
> ```

Vérifier après reboot :

```bash
groups
# doit inclure : video input render seat
```

---

## 6. Script de démarrage kiosk

```bash
nano /home/toto/kiosk.sh
```

```bash
#!/bin/bash
wayfire &
sleep 10
WAYLAND_DISPLAY=wayland-1 chromium \
  --ozone-platform=wayland \
  --disable-gpu \
  --disable-gpu-compositing \
  --kiosk \
  --noerrdialogs \
  --disable-infobars \
  --no-first-run \
  --disable-pinch \
  http://localhost:8080
```

```bash
chmod +x /home/toto/kiosk.sh
```

> **Note :** `--disable-gpu` et `--disable-gpu-compositing` sont obligatoires sur Pi 3B — le GPU VC4 ne supporte que OpenGL ES 2.0, Chromium requiert ES 3.0 par défaut.

---

## 7. Services systemd

### Service MagicMirror

> **Attention :** Node.js étant installé via nvm, il est hors du PATH système. Le chemin absolu de l'exécutable `node` doit être spécifié explicitement dans le service.

Récupérer le chemin absolu :

```bash
which node
# exemple : /home/toto/.nvm/versions/node/v26.3.0/bin/node
```

```bash
sudo nano /etc/systemd/system/magicmirror.service
```

```ini
[Unit]
Description=MagicMirror
After=network.target

[Service]
Type=simple
User=toto
WorkingDirectory=/home/toto/MagicMirror
Environment=PATH=/home/toto/.nvm/versions/node/v26.3.0/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=/home/toto/.nvm/versions/node/v26.3.0/bin/node --run server
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

> Adapter `/home/toto/.nvm/versions/node/v26.3.0/bin/node` avec le chemin retourné par `which node`.

### Service Kiosk

```bash
sudo nano /etc/systemd/system/kiosk.service
```

```ini
[Unit]
Description=Wayfire Kiosk
After=magicmirror.service seatd.service
Requires=seatd.service

[Service]
Type=simple
User=toto
WorkingDirectory=/home/toto
Environment=XDG_RUNTIME_DIR=/run/user/1000
Environment=HOME=/home/toto
TimeoutStartSec=60
ExecStart=/home/toto/kiosk.sh
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

> **Note :** `XDG_RUNTIME_DIR=/run/user/1000` — adapter le UID si l'utilisateur n'est pas `1000` (vérifier avec `id -u $USER`).

### Activation

```bash
sudo systemctl daemon-reload
sudo systemctl enable magicmirror kiosk
sudo systemctl start magicmirror
sudo systemctl start kiosk
```

### Vérification

```bash
sudo systemctl status magicmirror
# attendu : active (running) — "Ready to go! Please point your browser to: http://0.0.0.0:8080"

sudo systemctl status kiosk
# attendu : active (running) avec ~78 tâches (wayfire + processus chromium)
```

---

## 8. Vérification de l'affichage DSI

Wayfire détecte automatiquement l'écran DSI au démarrage. Vérifier dans les logs :

```bash
journalctl -u kiosk --no-pager | grep DSI
# attendu : 'DSI-1' connected — 800x480 @ 60.029 Hz
```

MagicMirror doit s'afficher sur l'écran DSI dans les 15 secondes suivant le démarrage du service kiosk.

---

## Notes techniques

| Sujet | Détail |
|---|---|
| Electron | Non utilisé — incompatible Pi 3B, erreur d'installation sur ARMv8 |
| Node.js via nvm | Hors PATH système — chemin absolu obligatoire dans les services systemd |
| GPU | VC4 V3D 2.1 — ES 2.0 uniquement, `--disable-gpu` obligatoire dans Chromium |
| EDID | `Failed to parse EDID` sur l'écran OSOYOO — sans impact fonctionnel |
| Erreurs dbus/UPower/GCM | Bénignes, n'affectent pas le fonctionnement |
| Accès réseau | MagicMirror accessible sur `http://<ip>:8080` depuis le réseau local |
| Node.js | v26.x validé — v22.x minimum requis par MagicMirror² |

---

## Arborescence finale

```
/home/toto/
├── MagicMirror/
│   ├── config/
│   │   └── config.js
│   ├── css/
│   │   └── custom.css
│   └── node_modules/
└── kiosk.sh

/etc/systemd/system/
├── magicmirror.service
└── kiosk.service
```
