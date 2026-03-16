# 📷 MotionEye — Docker + Pan-Tilt Servo Control

> **Surveillance caméra containerisée sur Debian/Raspberry Pi**  
> MotionEye dans Docker · Contrôle Pan-Tilt MG996R via PCA9685 I²C · API Flask · Interface PTZ web

---

## Table des matières

- [Architecture](#architecture)
- [Structure du projet](#structure-du-projet)
- [Prérequis](#prérequis)
  - [Matériel](#matériel)
  - [Logiciel](#logiciel)
- [Installation de Docker](#installation-de-docker)
- [Déploiement de MotionEye](#déploiement-de-motioneye)
- [Contrôle Pan-Tilt](#contrôle-pan-tilt)
  - [Matériel](#matériel)
  - [API Flask — servo_api.py](#api-flask--servo_apipy)
  - [Service systemd](#service-systemd)
  - [Intégration MotionEye — Action Buttons](#intégration-motioneye--action-buttons)
- [Interface PTZ web](#interface-ptz-web)
- [Intégration Home Assistant](#intégration-home-assistant)
- [Diagnostic et logs](#diagnostic-et-logs)
- [Configuration Wi-Fi](#configuration-wi-fi)
- [Ressources](#ressources)

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Raspberry Pi / Debian 11                │
│                                                         │
│   ┌─────────────────────┐    ┌────────────────────────┐ │
│   │  Docker Container   │    │  systemd Service       │ │
│   │                     │    │                        │ │
│   │  motioneye:latest   │◄───│  servo_api.py (Flask)  │ │
│   │  :8765 (UI)         │    │  :5000                 │ │
│   │  :8081 (stream)     │    │                        │ │
│   └──────────┬──────────┘    └──────────┬─────────────┘ │
│              │                          │               │
│         /dev/video*              I²C (SCL/SDA)          │
│              │                          │               │
│         [Caméra USB]              [PCA9685]             │
│                                    ├── CH0: PAN servo   │
│                                    └── CH4: TILT servo  │
└─────────────────────────────────────────────────────────┘
```

**Principes de l'architecture :**

- Debian reste propre : Python 2 et les dépendances MotionEye restent isolés dans le conteneur
- MotionEye accède aux périphériques caméra via `--device /dev/video*`
- L'API servo tourne en natif sur l'hôte et est accessible depuis le conteneur via `host.docker.internal:5000`
- Démarrage automatique garanti par `--restart=always` (Docker) et `systemd` (API servo)

---

## Structure du projet

```
/
├── opt/
│   └── motioneye/
│       ├── config/                  # Configuration MotionEye (volume Docker)
│       │   ├── left_1               # Script action bouton gauche
│       │   ├── right_1              # Script action bouton droite
│       │   └── preset1_1            # Script action bouton centre
│       └── media/                   # Médias enregistrés (volume Docker)
│           └── Camera1/
│               └── YYYY-MM-DD/      # Captures triées par date
│
├── home/
│   └── pi/
│       └── servo_control/
│           ├── servo_api.py         # API Flask contrôle Pan-Tilt
│           ├── servo_safe_stop.py   # Script d'arrêt propre (ExecStop systemd)
│           └── start.bash           # Script d'activation initial du service
│
├── etc/
│   ├── systemd/
│   │   └── system/
│   │       └── servo_api.service    # Service systemd API servo
│   ├── nginx/
│   │   ├── sites-available/
│   │   │   └── pantilt              # Vhost nginx interface PTZ
│   │   └── sites-enabled/
│   │       └── pantilt -> ...       # Lien symbolique d'activation
│   └── wpa_supplicant/
│       └── wpa_supplicant.conf      # Configuration Wi-Fi
│
└── var/
    └── www/
        └── html/
            ├── pantilt_control.html # Interface PTZ simple (boutons)
            └── pantilt_live.html    # Interface PTZ live (flux vidéo + PTZ)

# Home Assistant (si installé sur la même machine ou réseau)
/config/
└── configuration.yaml               # Déclaration rest_command PTZ
```

---

## Prérequis

### Matériel

| Qté | Composant | Référence / Remarque |
|---|---|---|
| 1× | Raspberry Pi 4 | Modèle B — 2 Go RAM minimum recommandé |
| 1× | Contrôleur PWM I²C | PCA9685PW — 16 canaux, adresse `0x40` par défaut |
| 2× | Servo-moteur | MG996R **180°** — 1× PAN (axe horizontal) + 1× TILT (axe vertical) |
| 1× | Support Pan-Tilt | *Servo Motor Bracket 2 DOF Short Long Pan And Tilt Sensor Mount Kit* — compatible MG995 / MG996 |
| 1× | Caméra | **Option A** — Raspberry Pi Camera Module IR Night Vision (interface CSI ribbon) — **utilisée dans ce projet** |
| | | **Option B** — Caméra USB Compatible Video4Linux (`/dev/video0`) — alternative valide |
| 1× | Alimentation servos | **5–6V / 3A minimum** dédiée (ne pas utiliser les 5V GPIO du Pi) |

> ⚠️ Les servos MG996R consomment jusqu'à **2.5A en charge par servo**. Toujours utiliser une alimentation **indépendante** sur la broche `V+` du PCA9685. Alimenter les servos depuis les 5V du Raspberry Pi provoque des chutes de tension et des redémarrages intempestifs.

> ⚠️ Le **MG996R 360°** est fonctionnel mais non recommandé pour un contrôle angulaire précis. Privilégier impérativement la version **180°** pour un positionnement absolu et reproductible.

> 📷 **Caméra CSI (Raspberry Pi Camera IR) :** la caméra ribbon native n'est pas un périphérique USB — elle n'apparaît pas dans `/dev/video*` par défaut. Elle nécessite l'activation du module `bcm2835-v4l2` pour être exposée comme `/dev/video0` et devenir compatible MotionEye/Video4Linux.
>
> Activer le module au démarrage :
> ```bash
> echo "bcm2835-v4l2" | sudo tee -a /etc/modules
> sudo reboot
> # Vérification après reboot :
> ls -l /dev/video*
> v4l2-ctl --list-devices
> ```
> Une fois le module chargé, la caméra CSI apparaît comme `/dev/video0` et s'utilise exactement comme une caméra USB dans la configuration Docker MotionEye.

### Logiciel

| Composant | Version recommandée |
|---|---|
| Debian | 11 (Bullseye) ou supérieur |
| Docker Engine | 24+ |
| Docker Compose | v2 |
| Python | 3.9+ |
| Flask | 2.x+ |
| adafruit-circuitpython-pca9685 | dernière version stable |

---

## Installation de Docker

```bash
# Installation via le script officiel
curl -fsSL https://get.docker.com | sudo sh

# Ajout de l'utilisateur courant au groupe docker
sudo usermod -aG docker $USER
newgrp docker

# Installation de docker-compose (v1 legacy, si nécessaire)
sudo apt install docker-compose
```

### Préparation des volumes MotionEye

Les données de configuration et les médias sont stockés hors du conteneur pour garantir la persistance entre les redémarrages.

```bash
sudo mkdir -p /opt/motioneye/{config,media}
sudo chown -R 1000:1000 /opt/motioneye
```

---

## Déploiement de MotionEye

Le script `install_motioneye.sh` automatise le déploiement complet.

### Utilisation

```bash
chmod +x install_motioneye.sh
sudo ./install_motioneye.sh
```

### Contenu du script

Avant de créer le script, identifier les périphériques caméra disponibles sur l'hôte :

```bash
ls -l /dev/video*
```

Exemple de sortie :

```
crw-rw----+ 1 root video 81, 0 jan 10 09:12 /dev/video0
crw-rw----+ 1 root video 81, 1 jan 10 09:12 /dev/video1
```

Chaque entrée `/dev/videoN` correspond à un périphérique de capture. Une même caméra USB peut exposer **plusieurs nœuds** (ex. `/dev/video0` et `/dev/video1`) — seul le premier nœud pair est généralement le flux vidéo principal. Pour identifier lequel est actif :

```bash
v4l2-ctl --list-devices
```

Reporter les nœuds identifiés dans les lignes `--device` du script ci-dessous.

```bash
cd /opt/motioneye && vi install_motioneye.sh
```

```bash
#!/usr/bin/env bash

# ================================
# MotionEye Docker Runner
# ================================
# Multi-caméra : ajuster les lignes --device selon le cas :
#   --device /dev/video0:/dev/video0
#   --device /dev/video1:/dev/video1
# ================================

set -e

CONTAINER_NAME="motioneye"
IMAGE="ghcr.io/motioneye-project/motioneye:latest"

CONFIG_DIR="/opt/motioneye/config"
MEDIA_DIR="/opt/motioneye/media"

mkdir -p "${CONFIG_DIR}"
mkdir -p "${MEDIA_DIR}"

# Suppression du conteneur existant si présent
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  echo "Conteneur ${CONTAINER_NAME} existant détecté, suppression..."
  docker rm -f "${CONTAINER_NAME}"
fi

docker run -d \
  --name "${CONTAINER_NAME}" \
  --restart=always \
  -p 8765:8765 \
  -p 8081:8081 \
  -e TZ=Europe/Zurich \
  -v "${CONFIG_DIR}:/etc/motioneye" \
  -v "${MEDIA_DIR}:/var/lib/motioneye" \
  -v /etc/localtime:/etc/localtime:ro \
  -v /etc/timezone:/etc/timezone:ro \
  --device /dev/video0:/dev/video0 \
  --device /dev/video1:/dev/video1 \
  --add-host=host.docker.internal:host-gateway \
  "${IMAGE}"

echo "MotionEye est lancé."
echo "Interface web : http://localhost:8765"
```

### Accès à l'interface

| Service | URL |
|---|---|
| Interface web MotionEye | `http://<IP>:8765` |
| Flux vidéo MJPEG | `http://<IP>:8081` |

### Alias utiles

Ajouter dans `~/.bash_aliases` :

```bash
cd ~ && vi .bash_aliases
```

```bash
# Accès aux médias dans le conteneur
alias camera='docker exec -it -w /var/lib/motioneye/Camera1 motioneye bash'

# Copie des images du conteneur vers l'hôte
alias images='docker cp motioneye:/var/lib/motioneye/Camera1/. /home/pi/timelapse/'

# Statistiques fichiers / espace disque
alias camera-stats='find /opt/motioneye/media/Camera1/ -type f -printf "." | wc -c | awk "{print \"Fichiers : \" \$1}"; du -sh /opt/motioneye/media/Camera1/'
```

---

## Contrôle Pan-Tilt

### Matériel

| Composant | Rôle | Canal PCA9685 |
|---|---|---|
| MG996R (bas) | Rotation horizontale (PAN) | CH 0 |
| MG996R (haut) | Inclinaison verticale (TILT) | CH 4 |
| PCA9685 | Contrôleur PWM I²C 16 canaux | `0x40` |

**Câblage I²C (Raspberry Pi) :**

| PCA9685 | GPIO RPi |
|---|---|
| SDA | GPIO 2 (Pin 3) |
| SCL | GPIO 3 (Pin 5) |
| VCC | 3.3V |
| GND | GND |
| V+ | 5–6V (alimentation servos, séparée) |

> ⚠️ Les servos MG996R consomment jusqu'à 2.5A en charge. Utiliser une **alimentation dédiée 5–6V** pour V+, ne jamais alimenter les servos depuis les 5V du Raspberry Pi.

### Calibration servo MG996R 180°

Les valeurs d'impulsion varient selon les fabricants. Procédure recommandée :

1. Démarrer avec `SERVO_MIN_US=700` et `SERVO_MAX_US=2300`
2. Tester `angle=0` et `angle=180`
3. Si le servo force en butée (bruit mécanique), réduire la plage (ex. : `800–2200`)
4. Un servo correctement calibré atteint ses extrêmes **sans vibration ni bruit de contrainte**

Pour restreindre la plage de mouvement, modifier uniquement ces constantes dans `servo_api.py` :

```python
ANGLE_MIN = 0
ANGLE_MAX = 45
DEFAULT_ANGLE = 22.5
```

---

### API Flask — servo_api.py

```bash
cd /home/pi/servo_control && vi servo_api.py
```

<details>
<summary>📄 Voir le code complet — servo_api.py</summary>

```python
#!/usr/bin/env python3
from flask import Flask, jsonify
import time
import threading
import board
import busio
from adafruit_pca9685 import PCA9685

# =========================
# CONFIG GÉNÉRALE
# =========================
PWM_FREQ_HZ = 50

PAN_CHANNEL  = 0   # moteur bas (rotation horizontale)
TILT_CHANNEL = 4   # moteur haut (inclinaison verticale)

PAN_INVERTED = True        # inversion logique du sens PAN
IDLE_DISABLE_S = 3.0       # coupure PWM après 3s d'inactivité

# =========================
# LIMITES MÉCANIQUES
# =========================
PAN_MIN_ANGLE  = 10
PAN_MAX_ANGLE  = 160

TILT_MIN_ANGLE = 10
TILT_MAX_ANGLE = 160

STEP_DEG = 5
MIN_INTERVAL_S = 0.05

# =========================
# CALIBRATION SERVO MG996R
# =========================
SERVO_MIN_US    = 700
SERVO_CENTER_US = 1500
SERVO_MAX_US    = 2300

# =========================
# INITIALISATION FLASK
# =========================
app = Flask(__name__)
_lock = threading.Lock()
_last_ts = 0.0


def rate_limit():
    """Limite le taux d'appels pour éviter les commandes trop rapprochées."""
    global _last_ts
    now = time.time()
    if now - _last_ts < MIN_INTERVAL_S:
        return False
    _last_ts = now
    return True


def clamp(v, vmin, vmax):
    """Limite une valeur entre vmin et vmax."""
    return max(vmin, min(vmax, v))


def angle_to_duty(angle, freq):
    """Convertit un angle (0–180°) en duty cycle PWM 16-bit (0–65535)."""
    angle = clamp(angle, 0, 180)
    pulse_us = SERVO_MIN_US + (angle / 180.0) * (SERVO_MAX_US - SERVO_MIN_US)
    period_us = 1_000_000 / freq
    duty = int((pulse_us / period_us) * 65535)
    return clamp(duty, 0, 65535)


class PanTilt:
    """Contrôleur Pan-Tilt avec PCA9685 et servos MG996R."""

    def __init__(self):
        i2c = busio.I2C(board.SCL, board.SDA)
        self.pca = PCA9685(i2c)
        self.pca.frequency = PWM_FREQ_HZ

        self.pan  = self.pca.channels[PAN_CHANNEL]
        self.tilt = self.pca.channels[TILT_CHANNEL]

        self._last_pan_duty  = None
        self._last_tilt_duty = None

        self.pan_angle  = 90
        self.tilt_angle = 90

        self.last_activity_ts = time.time()
        self.pwm_enabled = True

        self.apply()

    def apply(self):
        """Applique les angles courants aux servos."""
        if not self.pwm_enabled:
            self.pwm_enabled = True

        self.last_activity_ts = time.time()

        pan_angle = (180 - self.pan_angle) if PAN_INVERTED else self.pan_angle
        pan_duty = angle_to_duty(pan_angle, PWM_FREQ_HZ)
        if pan_duty != self._last_pan_duty:
            self.pan.duty_cycle = pan_duty
            self._last_pan_duty = pan_duty

        tilt_duty = angle_to_duty(self.tilt_angle, PWM_FREQ_HZ)
        if tilt_duty != self._last_tilt_duty:
            self.tilt.duty_cycle = tilt_duty
            self._last_tilt_duty = tilt_duty

    def center(self):
        """Recentre le Pan-Tilt à 90°/90°."""
        self.pan_angle  = 90
        self.tilt_angle = 90
        self.apply()

    def pan_move(self, delta):
        """Déplace le PAN de delta degrés."""
        self.pan_angle = clamp(self.pan_angle + delta, PAN_MIN_ANGLE, PAN_MAX_ANGLE)
        self.apply()

    def tilt_move(self, delta):
        """Déplace le TILT de delta degrés."""
        self.tilt_angle = clamp(self.tilt_angle + delta, TILT_MIN_ANGLE, TILT_MAX_ANGLE)
        self.apply()

    def disable(self):
        """Désactive les signaux PWM pour économiser l'énergie."""
        if not self.pwm_enabled:
            return
        self.pan.duty_cycle  = 0
        self.tilt.duty_cycle = 0
        self._last_pan_duty  = None
        self._last_tilt_duty = None
        self.pwm_enabled = False


def idle_watchdog():
    """Thread de surveillance : désactive les servos après inactivité."""
    while True:
        time.sleep(0.2)
        if ctrl is None:
            continue
        if ctrl.pwm_enabled and (time.time() - ctrl.last_activity_ts) > IDLE_DISABLE_S:
            ctrl.disable()


# =========================
# INITIALISATION CONTRÔLEUR
# =========================
ctrl = PanTilt()
threading.Thread(target=idle_watchdog, daemon=True).start()


# =========================
# ROUTES HTTP
# =========================

@app.route("/status", methods=["GET"])
def status():
    return jsonify(pan_angle=ctrl.pan_angle, tilt_angle=ctrl.tilt_angle, pwm_enabled=ctrl.pwm_enabled)

@app.route("/center", methods=["POST", "GET"])
def center():
    with _lock:
        ctrl.center()
    return jsonify(ok=True, action="center")

@app.route("/pan/left", methods=["POST", "GET"])
def pan_left():
    if not rate_limit():
        return jsonify(ok=True, skipped=True)
    with _lock:
        ctrl.pan_move(-STEP_DEG)
    return jsonify(ok=True, pan=ctrl.pan_angle)

@app.route("/pan/right", methods=["POST", "GET"])
def pan_right():
    if not rate_limit():
        return jsonify(ok=True, skipped=True)
    with _lock:
        ctrl.pan_move(STEP_DEG)
    return jsonify(ok=True, pan=ctrl.pan_angle)

@app.route("/tilt/up", methods=["POST", "GET"])
def tilt_up():
    if not rate_limit():
        return jsonify(ok=True, skipped=True)
    with _lock:
        ctrl.tilt_move(STEP_DEG)
    return jsonify(ok=True, tilt=ctrl.tilt_angle)

@app.route("/tilt/down", methods=["POST", "GET"])
def tilt_down():
    if not rate_limit():
        return jsonify(ok=True, skipped=True)
    with _lock:
        ctrl.tilt_move(-STEP_DEG)
    return jsonify(ok=True, tilt=ctrl.tilt_angle)

# Alias de compatibilité MotionEye / UI legacy
@app.route("/left",  methods=["GET", "POST"])
def left_alias():  return pan_left()

@app.route("/right", methods=["GET", "POST"])
def right_alias(): return pan_right()

@app.route("/up",   methods=["GET", "POST"])
def up_alias():    return tilt_up()

@app.route("/down", methods=["GET", "POST"])
def down_alias():  return tilt_down()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
```

</details>

#### Endpoints de l'API

| Méthode | Endpoint | Description |
|---|---|---|
| `GET` | `/status` | État courant (angles, PWM actif) |
| `POST/GET` | `/pan/left` | PAN vers la gauche (−5°) |
| `POST/GET` | `/pan/right` | PAN vers la droite (+5°) |
| `POST/GET` | `/tilt/up` | TILT vers le haut (+5°) |
| `POST/GET` | `/tilt/down` | TILT vers le bas (−5°) |
| `POST/GET` | `/center` | Recentrage à 90°/90° |
| `POST/GET` | `/left` `/right` `/up` `/down` | Alias de compatibilité MotionEye |

#### Tests rapides (depuis le Pi)

```bash
curl http://localhost:5000/status
curl -X POST http://localhost:5000/center
curl -X POST http://localhost:5000/pan/left
curl -X POST http://localhost:5000/pan/right
curl -X POST http://localhost:5000/tilt/up
curl -X POST http://localhost:5000/tilt/down
```

---

### Service systemd

```bash
cd /etc/systemd/system && vi servo_api.service
```

```ini
[Unit]
Description=Servo Control API for MotionEye
After=network.target
Wants=i2c.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/servo_control
ExecStart=/usr/bin/python3 /home/pi/servo_control/servo_api.py
ExecStop=/usr/bin/python3 /home/pi/servo_control/servo_safe_stop.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

#### Activation

```bash
sudo systemctl daemon-reload
sudo systemctl enable servo_api.service
sudo systemctl start servo_api.service
sudo systemctl status servo_api.service
```

#### Script d'activation initial (`start.bash`)

```bash
cd /home/pi/servo_control && vi start.bash
```

```bash
#!/bin/bash
echo "Rechargement systemd..."
sudo systemctl daemon-reload && sleep 2

echo "Activation du service..."
sudo systemctl enable servo_api.service && sleep 1

echo "Démarrage du service..."
sudo systemctl start servo_api.service && sleep 3

echo "Statut :"
sudo systemctl status servo_api.service
```

---

### Intégration MotionEye — Action Buttons

MotionEye génère des boutons d'action sur le flux vidéo si des scripts exécutables nommés `[action]_[cameraid]` sont présents dans `/opt/motioneye/config/`.

> L'ID de la caméra est `1` par défaut si une seule caméra est configurée.

**Vérification réseau depuis le conteneur avant création des scripts :**

```bash
docker exec -it motioneye sh -lc 'python3 - << "PY"
import urllib.request
req = urllib.request.Request("http://host.docker.internal:5000/left", method="POST")
print(urllib.request.urlopen(req, timeout=2).read().decode())
PY'
# Réponse attendue : {"status":"ok",...}
```

**Création des scripts d'action :**

```bash
cd /opt/motioneye/config && vi left_1
```

```bash
# Gauche → left_1
sudo tee /opt/motioneye/config/left_1 > /dev/null <<'SH'
#!/bin/sh
python3 - << "PY"
import urllib.request
urllib.request.urlopen(
    urllib.request.Request("http://host.docker.internal:5000/left", method="POST"),
    timeout=2
).read()
PY
SH
sudo chmod +x /opt/motioneye/config/left_1
```

```bash
cd /opt/motioneye/config && vi right_1
```

```bash
# Droite → right_1
sudo tee /opt/motioneye/config/right_1 > /dev/null <<'SH'
#!/bin/sh
python3 - << "PY"
import urllib.request
urllib.request.urlopen(
    urllib.request.Request("http://host.docker.internal:5000/right", method="POST"),
    timeout=2
).read()
PY
SH
sudo chmod +x /opt/motioneye/config/right_1
```

```bash
cd /opt/motioneye/config && vi preset1_1
```

```bash
# Centre → preset1_1  (pas d'action "center" native dans MotionEye)
sudo tee /opt/motioneye/config/preset1_1 > /dev/null <<'SH'
#!/bin/sh
python3 - << "PY"
import urllib.request
urllib.request.urlopen(
    urllib.request.Request("http://host.docker.internal:5000/center", method="POST"),
    timeout=2
).read()
PY
SH
sudo chmod +x /opt/motioneye/config/preset1_1
```

> **Note :** MotionEye ne supporte pas le press-and-hold. Chaque clic déclenche un micro-déplacement (`STEP_DEG = 5°`). Les déplacements fins s'obtiennent par clics répétés.

---

## Interface PTZ web

Une interface HTML autonome permet le contrôle Pan-Tilt depuis n'importe quel navigateur sur le réseau local, hébergée sur nginx ou Apache installé sur le Raspberry Pi.

### Installation du serveur web

```bash
# nginx (recommandé, léger)
sudo apt install nginx -y
sudo systemctl enable nginx
sudo systemctl start nginx

# Apache (alternative)
sudo apt install apache2 -y
sudo systemctl enable apache2
sudo systemctl start apache2
```

---

### Version simple (boutons uniquement)

Interface minimaliste : boutons directionnels sans flux vidéo intégré. Idéale pour tester l'API ou pour un accès depuis un appareil mobile bas de gamme.

```bash
cd /var/www/html && vi pantilt_control.html
```

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Pan-Tilt Control</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }
        button { width: 80px; height: 80px; font-size: 24px; margin: 10px; }
    </style>
</head>
<body>
    <h1>Pan-Tilt Control</h1>

    <div>
        <button onclick="send('/tilt/up')">⬆</button>
    </div>
    <div>
        <button onclick="send('/pan/left')">⬅</button>
        <button onclick="send('/center')">⭕</button>
        <button onclick="send('/pan/right')">➡</button>
    </div>
    <div>
        <button onclick="send('/tilt/down')">⬇</button>
    </div>

    <script>
        const baseUrl = "http://<IP_DU_PI>:5000";

        function send(route) {
            fetch(baseUrl + route, { method: "POST" })
                .then(() => console.log("OK:", route))
                .catch(err => console.error("Erreur:", err));
        }
    </script>
</body>
</html>
```

---

### Version Live (flux vidéo + contrôles PTZ)

Interface complète : flux MotionEye intégré en 1280×720, contrôles PTZ, support clavier, indicateur de connexion API, responsive mobile/tablette.

**Fonctionnalités :**
- Flux vidéo intégré en direct (iframe MotionEye port `8081`)
- Boutons directionnels PTZ + recentrage
- Contrôle clavier : `←` `→` `↑` `↓` + `Espace` (centre)
- Indicateur de connexion API en temps réel
- Responsive (adaptatif mobile/tablette)

```bash
cd /var/www/html && vi pantilt_live.html
```

<details>
<summary>📄 Voir le code complet — pantilt_live.html</summary>

```html
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PTZ Live Control</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            background: linear-gradient(135deg, #0f0f1e 0%, #1a1a2e 100%);
            color: #e0e0e0;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            height: 100vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        header { text-align: center; padding: 15px 20px; flex-shrink: 0; }

        h1 {
            font-size: 24px;
            font-weight: 300;
            letter-spacing: 2px;
            color: #ffffff;
            text-transform: uppercase;
            border-bottom: 2px solid #4a9eff;
            padding-bottom: 8px;
            display: inline-block;
        }

        .container {
            display: flex;
            gap: 30px;
            padding: 20px;
            flex: 1;
            min-height: 0;
            justify-content: center;
            align-items: center;
        }

        .video-wrapper {
            background: #16213e;
            border-radius: 12px;
            padding: 15px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
            border: 1px solid #2a3f5f;
            display: flex;
            flex-direction: column;
            max-height: 100%;
        }

        .video-header {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 12px;
            padding-bottom: 10px;
            border-bottom: 1px solid #2a3f5f;
            flex-shrink: 0;
        }

        .status-indicator {
            width: 10px;
            height: 10px;
            background: #4ade80;
            border-radius: 50%;
            box-shadow: 0 0 10px #4ade80;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .video-title {
            font-size: 13px;
            color: #9ca3af;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .video-container {
            flex: 1;
            min-height: 0;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        iframe {
            width: 1280px;
            height: 720px;
            max-width: 100%;
            max-height: 100%;
            border: none;
            background: #000;
            border-radius: 8px;
            display: block;
        }

        .controls-wrapper {
            background: #16213e;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
            border: 1px solid #2a3f5f;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
        }

        .controls-title {
            font-size: 15px;
            color: #9ca3af;
            margin-bottom: 20px;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            font-weight: 500;
        }

        .controls { display: flex; flex-direction: column; gap: 10px; user-select: none; }

        .row { display: flex; justify-content: center; gap: 10px; }

        button {
            width: 75px;
            height: 75px;
            font-size: 30px;
            background: linear-gradient(145deg, #1e3a5f, #16213e);
            color: #ffffff;
            border: 1px solid #4a9eff;
            border-radius: 12px;
            cursor: pointer;
            transition: all 0.2s ease;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        }

        button:hover {
            background: linear-gradient(145deg, #2a4a7f, #1e3a5f);
            border-color: #6bb6ff;
            box-shadow: 0 6px 20px rgba(74,158,255,0.4);
            transform: translateY(-2px);
        }

        button:active { transform: translateY(0); }

        button.center-btn {
            background: linear-gradient(145deg, #5f1e3a, #3e1621);
            border-color: #ff4a9e;
        }

        button.center-btn:hover {
            background: linear-gradient(145deg, #7f2a4a, #5f1e3a);
            border-color: #ff6bb6;
            box-shadow: 0 6px 20px rgba(255,74,158,0.4);
        }

        .hint {
            margin-top: 20px;
            font-size: 12px;
            color: #6b7280;
            text-align: center;
            padding: 10px 15px;
            background: rgba(0,0,0,0.3);
            border-radius: 8px;
            border: 1px solid #2a3f5f;
            line-height: 1.5;
        }

        .hint strong { color: #4a9eff; font-weight: 600; }

        .connection-status {
            margin-top: 12px;
            padding: 6px 12px;
            background: rgba(74,222,128,0.1);
            border: 1px solid #4ade80;
            border-radius: 6px;
            font-size: 11px;
            color: #4ade80;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .connection-status.error {
            background: rgba(239,68,68,0.1);
            border-color: #ef4444;
            color: #ef4444;
        }

        @media (max-width: 1400px) { iframe { width: 960px; height: 540px; } }
        @media (max-width: 1100px) { iframe { width: 640px; height: 360px; } }
        @media (max-width: 768px) {
            .container { flex-direction: column; overflow-y: auto; }
            body { overflow-y: auto; }
            iframe { width: 100%; height: auto; aspect-ratio: 16/9; }
        }
    </style>
</head>
<body>
    <header>
        <h1>Pan-Tilt Live Control</h1>
    </header>

    <div class="container">
        <!-- FLUX VIDÉO -->
        <div class="video-wrapper">
            <div class="video-header">
                <div class="status-indicator"></div>
                <span class="video-title">Flux vidéo en direct — 1280×720</span>
            </div>
            <div class="video-container">
                <!-- Remplacer l'IP par celle du Raspberry Pi -->
                <iframe src="http://<IP_DU_PI>:8081/" allowfullscreen></iframe>
            </div>
        </div>

        <!-- COMMANDES PTZ -->
        <div class="controls-wrapper">
            <div class="controls-title">Commandes PTZ</div>
            <div class="controls">
                <div class="row">
                    <button onclick="send('/up')" title="Haut (↑)">⬆</button>
                </div>
                <div class="row">
                    <button onclick="send('/left')"  title="Gauche (←)">⬅</button>
                    <button class="center-btn" onclick="send('/center')" title="Centre (Espace)">⭕</button>
                    <button onclick="send('/right')" title="Droite (→)">➡</button>
                </div>
                <div class="row">
                    <button onclick="send('/down')" title="Bas (↓)">⬇</button>
                </div>
            </div>
            <div class="hint">
                <strong>Clavier :</strong> ↑ ↓ ← →<br>
                <strong>Espace</strong> = centre
            </div>
            <div class="connection-status" id="status">● Connecté à l'API</div>
        </div>
    </div>

    <script>
        // Remplacer l'IP par celle du Raspberry Pi
        const apiBase = "http://<IP_DU_PI>:5000";

        let keyLock = false;
        const KEY_DELAY_MS = 120;
        const statusEl = document.getElementById('status');

        function send(route) {
            fetch(apiBase + route, { method: "POST" })
                .then(r => {
                    updateStatus(r.ok);
                    return r.json();
                })
                .catch(() => updateStatus(false));
        }

        function updateStatus(connected) {
            if (connected) {
                statusEl.className = 'connection-status';
                statusEl.textContent = '● Connecté à l\'API';
            } else {
                statusEl.className = 'connection-status error';
                statusEl.textContent = '● Erreur de connexion';
            }
        }

        // Test de connexion au chargement de la page
        fetch(apiBase + '/status')
            .then(() => updateStatus(true))
            .catch(() => updateStatus(false));

        // Gestion clavier
        document.addEventListener("keydown", (e) => {
            if (keyLock) return;
            const map = {
                ArrowUp:    "/up",
                ArrowDown:  "/down",
                ArrowLeft:  "/left",
                ArrowRight: "/right",
                " ":        "/center"
            };
            if (map[e.key]) {
                send(map[e.key]);
                keyLock = true;
                setTimeout(() => keyLock = false, KEY_DELAY_MS);
                e.preventDefault();
            }
        });
    </script>
</body>
</html>
```

</details>

---

### Configuration nginx (vhost dédié)

Pour exposer l'interface sur un port ou un sous-domaine dédié :

```bash
cd /etc/nginx/sites-available && vi pantilt
```

```nginx
server {
    listen 8080;
    server_name _;

    root /var/www/html;
    index pantilt_live.html;

    location / {
        try_files $uri $uri/ =404;
    }
}
```

```bash
# Activation du vhost
sudo ln -s /etc/nginx/sites-available/pantilt /etc/nginx/sites-enabled/pantilt
sudo nginx -t
sudo systemctl reload nginx
```

| Interface | URL d'accès |
|---|---|
| Version simple | `http://<IP_DU_PI>/pantilt_control.html` |
| Version Live | `http://<IP_DU_PI>/pantilt_live.html` |
| Via vhost dédié | `http://<IP_DU_PI>:8080` |

> **Adapter l'IP** : remplacer `<IP_DU_PI>` par l'adresse réelle du Raspberry Pi dans les deux fichiers HTML (balise `<iframe src=...>` et variable `const apiBase`).

---

## Intégration Home Assistant

### 1. Ajout de la caméra (flux MJPEG)

Depuis l'interface Home Assistant :

**Paramètres** → **Appareils et services** → **Ajouter une intégration** → rechercher **`MJPEG IP Camera`** → **Ajouter une entrée**

Renseigner les champs suivants :

| Champ | Valeur |
|---|---|
| **Nom** | `Camera Balcon` (ou autre) |
| **URL du flux MJPEG** | `http://<IP_DU_PI>:8081/` |
| **URL de l'image fixe** | `http://<IP_DU_PI>:8081/?action=snapshot` |
| **Authentification** | Aucune (laisser vide) |

> Remplacer `<IP_DU_PI>` par l'adresse IP réelle du Raspberry Pi sur le réseau local.

---

### 2. Commandes REST PTZ — configuration.yaml

Les commandes de contrôle Pan-Tilt sont déclarées via `rest_command` dans le fichier de configuration principal de Home Assistant.

```bash
cd /config && vi configuration.yaml
```

```yaml
##########################################
# LIVE CAMERA CONTROL BALCON
##########################################
rest_command:
  ptz_up:
    url: "http://<IP_DU_PI>:5000/up"
    method: POST
  ptz_down:
    url: "http://<IP_DU_PI>:5000/down"
    method: POST
  ptz_left:
    url: "http://<IP_DU_PI>:5000/left"
    method: POST
  ptz_right:
    url: "http://<IP_DU_PI>:5000/right"
    method: POST
  ptz_center:
    url: "http://<IP_DU_PI>:5000/center"
    method: POST
```

Après modification, recharger la configuration :

**Outils de développement** → **YAML** → **Recharger toute la configuration YAML**

ou via le menu **Paramètres** → **Système** → **Redémarrer**.

---

### 3. Dashboard — carte de contrôle PTZ

Dans le tableau de bord Home Assistant, ajouter une carte de type **Grille manuelle** avec le contenu YAML suivant :

**Tableau de bord** → **Modifier** → **Ajouter une carte** → **Manuel**

```yaml
type: grid
columns: 3
cards:
  - type: button
    name: Haut
    icon: mdi:arrow-up
    tap_action:
      action: call-service
      service: rest_command.ptz_up
  - type: button
    name: Centre
    icon: mdi:circle
    tap_action:
      action: call-service
      service: rest_command.ptz_center
  - type: button
    name: Bas
    icon: mdi:arrow-down
    tap_action:
      action: call-service
      service: rest_command.ptz_down
  - type: button
    name: Gauche
    icon: mdi:arrow-left
    tap_action:
      action: call-service
      service: rest_command.ptz_left
  - type: button
    name: Droite
    icon: mdi:arrow-right
    tap_action:
      action: call-service
      service: rest_command.ptz_right
```

Le rendu produit une grille 3 colonnes avec les boutons directionnels PTZ :

```
[ ↑  Haut  ] [ ⭕ Centre ] [ ↓  Bas   ]
[ ←  Gauche] [           ] [ →  Droite]
```

> **Note :** pour ajouter le flux vidéo au-dessus des boutons sur le même tableau de bord, ajouter une carte **Image** ou **Caméra** pointant vers l'entité créée à l'étape 1.

---

## Diagnostic et logs

```bash
# Logs MotionEye (conteneur)
docker logs motioneye --tail=200
docker logs -f motioneye

# Périphériques caméra disponibles
ls -l /dev/video*

# Logs API servo (systemd)
sudo journalctl -u servo_api.service -n 100 --no-pager
sudo systemctl status servo_api.service
```

---

## Configuration Wi-Fi

Applicable sur Debian 11 / Raspberry Pi sans NetworkManager.

### 1. Fichier wpa_supplicant

```bash
cd /etc/wpa_supplicant && vi wpa_supplicant.conf
```

```ini
country=CH
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={
    ssid="NOM_DU_WIFI"
    psk="MOT_DE_PASSE_WIFI"
    key_mgmt=WPA-PSK
}
```

> ⚠️ Le paramètre `country` est obligatoire pour l'activation des fréquences radio.

### 2. Sécurisation (obligatoire)

```bash
sudo chown root:root /etc/wpa_supplicant/wpa_supplicant.conf
sudo chmod 600 /etc/wpa_supplicant/wpa_supplicant.conf
```

### 3. Déblocage RF-Kill

```bash
sudo rfkill unblock wifi
rfkill list
# Résultat attendu :
#   Soft blocked: no
#   Hard blocked: no
```

### 4. Activation de l'interface

```bash
sudo ip link set wlan0 up
ip a show wlan0
```

### 5. Démarrage dhcpcd

```bash
sudo systemctl enable dhcpcd
sudo systemctl start dhcpcd
sudo wpa_cli -i wlan0 reconfigure
```

### 6. Priorité Wi-Fi sur Ethernet

```bash
cd /etc && vi dhcpcd.conf
```

Ajouter :

```
interface wlan0
metric 100

interface eth0
metric 200
```

```bash
sudo systemctl restart dhcpcd
```

> **Règle :** métrique plus basse = priorité plus haute. `wlan0 (100)` sera préféré à `eth0 (200)`.

### Commandes de diagnostic

```bash
ip a show wlan0
iw dev wlan0 link
journalctl -u wpa_supplicant -n 50
journalctl -u dhcpcd -n 50
ping -c 3 8.8.8.8
```

---

*Testé sur Raspberry Pi 4B · Debian 11 Bullseye · Docker 24 · Python 3.9*
