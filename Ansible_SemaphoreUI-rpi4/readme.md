# Ansible - Semaphore UI — Déploiement Production sur Raspberry Pi 4 avec Docker V2

> **Stack** : Semaphore UI v2.17.x · PostgreSQL 16 · Nginx (HTTPS auto-signé) · Docker Compose v2  
> **Cible** : Raspberry Pi 4 (arm64) · LAN privé · Gestion Ansible multi-nœuds  
> **Hôte** : `user@10.0.0.20` · Répertoire : `/home/user/semaphore`  
> **Révision** : 2026-03-17

---

## Table des matières

- [Ansible - Semaphore UI — Déploiement Production sur Raspberry Pi 4 avec Docker V2](#ansible---semaphore-ui--déploiement-production-sur-raspberry-pi-4-avec-docker-v2)
  - [Table des matières](#table-des-matières)
  - [1. Prérequis](#1-prérequis)
  - [2. Structure du projet](#2-structure-du-projet)
  - [3. Fichiers de configuration](#3-fichiers-de-configuration)
    - [3.1 `.env`](#31-env)
    - [3.2 `docker-compose.yml`](#32-docker-composeyml)
    - [3.3 `nginx/nginx.conf`](#33-nginxnginxconf)
    - [3.4 `scripts/gen-cert.sh`](#34-scriptsgen-certsh)
    - [3.5 `backup/backup.sh`](#35-backupbackupsh)
    - [3.6 `gitconfig-system`](#36-gitconfig-system)
  - [4. Procédure de déploiement](#4-procédure-de-déploiement)
  - [5. Configuration SSH Ansible](#5-configuration-ssh-ansible)
    - [5.1 Génération de la paire de clés](#51-génération-de-la-paire-de-clés)
    - [5.2 Distribution sur les nœuds cibles](#52-distribution-sur-les-nœuds-cibles)
    - [5.3 Vérification de l'accès SSH](#53-vérification-de-laccès-ssh)
  - [6. Gestion des playbooks et scripts](#6-gestion-des-playbooks-et-scripts)
    - [6.1 Contraintes d'ownership](#61-contraintes-downership)
    - [6.2 Procédure de commit](#62-procédure-de-commit)
    - [6.3 Exemple — script APT check](#63-exemple--script-apt-check)
  - [7. Configuration dans Semaphore UI](#7-configuration-dans-semaphore-ui)
    - [7.1 Key Store](#71-key-store)
    - [7.2 Inventory](#72-inventory)
    - [7.3 Variable Groups](#73-variable-groups)
    - [7.4 Repository](#74-repository)
    - [7.5 Task Template — Bash Script](#75-task-template--bash-script)
  - [8. Gestion des sauvegardes](#8-gestion-des-sauvegardes)
    - [Dump manuel immédiat](#dump-manuel-immédiat)
    - [Restauration](#restauration)
    - [Vérification du cron de backup](#vérification-du-cron-de-backup)
  - [9. Confiance au certificat TLS](#9-confiance-au-certificat-tls)
    - [Linux (clients sur le LAN)](#linux-clients-sur-le-lan)
    - [Firefox](#firefox)
    - [Chrome / Chromium](#chrome--chromium)
  - [10. Commandes d'exploitation](#10-commandes-dexploitation)
  - [11. Création de tâches Ansible](#11-création-de-tâches-ansible)
    - [Playbook `apt_upgrade.yml`](#playbook-apt_upgradeyml)
    - [Task Template Ansible](#task-template-ansible)
    - [Planification (Schedule)](#planification-schedule)
    - [Bash vs Ansible — choix rapide](#bash-vs-ansible--choix-rapide)
  - [12. Coexistence avec d'autres stacks Docker](#12-coexistence-avec-dautres-stacks-docker)
  - [13. Sécurité et recommandations](#13-sécurité-et-recommandations)

---

## 1. Prérequis

| Composant | Version minimale | Notes |
|---|---|---|
| Raspberry Pi OS | Bookworm 64-bit | arm64 obligatoire |
| Docker Engine | 24.x+ | `curl -fsSL https://get.docker.com \| sh` |
| Docker Compose | v2.x+ | Inclus avec Docker Engine (plugin) |
| OpenSSL | 3.x | Préinstallé sur Bookworm |
| Ansible | 2.14+ | Installé sur le Pi hôte (contrôleur) |

```bash
# Vérification rapide
docker --version && docker compose version && openssl version
```

> ⚠️ **Docker Compose v2** : la commande est `docker compose` (sans tiret). Le champ `version:` en tête de `docker-compose.yml` est obsolète — ne pas l'inclure.

---

## 2. Structure du projet

```
/home/user/semaphore/
├── .env                      ← Variables d'environnement (non versionné)
├── docker-compose.yml        ← Définition de la stack
├── gitconfig-system          ← Config Git système montée dans le container
├── nginx/
│   ├── nginx.conf            ← Configuration reverse proxy
│   └── ssl/
│       ├── semaphore.crt     ← Certificat auto-signé (généré)
│       └── semaphore.key     ← Clé privée (générée)
├── scripts/
│   └── gen-cert.sh           ← Script de génération TLS
├── backup/
│   └── backup.sh             ← Script de dump PostgreSQL (cron container)
├── ssh_keys/                 ← Clés SSH Ansible (montées en lecture seule)
│   ├── semaphore_ansible     ← Clé privée
│   └── semaphore_ansible.pub ← Clé publique (déployée sur les nœuds)
├── playbooks/                ← Scripts et playbooks Ansible (repo Git local)
│   ├── apt_check.sh          ← Exemple : vérification APT sur nœud distant
│   └── apt_upgrade.yml       ← Exemple : upgrade APT via Ansible
└── backups/                  ← Dumps PostgreSQL automatiques
```

```bash
mkdir -p /home/user/semaphore/{nginx/ssl,scripts,backup,backups,ssh_keys,playbooks}
cd /home/user/semaphore
```

---

## 3. Fichiers de configuration

### 3.1 `.env`

> ⚠️ **Ce fichier ne doit jamais être versionné.** Ajouter `.env` à `.gitignore`.

```env
# ── PostgreSQL ────────────────────────────────────────────
POSTGRES_USER=semaphore
POSTGRES_PASSWORD=CHANGE_ME_STRONG_PASSWORD
POSTGRES_DB=semaphore

# ── Compte administrateur Semaphore ──────────────────────
SEMAPHORE_ADMIN=admin
SEMAPHORE_ADMIN_PASSWORD=CHANGE_ME_ADMIN_PASSWORD
SEMAPHORE_ADMIN_NAME=Administrateur
SEMAPHORE_ADMIN_EMAIL=admin@lan.local

# ── Chiffrement des clés d'accès (32 chars min) ───────────
# Générer : openssl rand -base64 32
SEMAPHORE_ACCESS_KEY_ENCRYPTION=CHANGE_ME_32CHARS_RANDOM_STRING

# ── Clés SSH du contrôleur (montées en lecture seule) ────
SSH_KEYS_PATH=/home/user/semaphore/ssh_keys

# ── Réseau LAN ───────────────────────────────────────────
SERVER_CN=semaphore.lan
SERVER_IP=10.0.0.20
```

---

### 3.2 `docker-compose.yml`

> **Ports** : la stack utilise `9080`/`9443` pour éviter les conflits avec d'autres stacks actives (voir [section 12](#12-coexistence-avec-dautres-stacks-docker)).  
> **`user: "0"`** : le container semaphore démarre en root pour que le fichier `/etc/gitconfig` soit accessible à tous les sous-processus Git lancés par Semaphore lors de l'exécution des tâches.

```yaml
# ================================================================
# Semaphore UI — Stack production Raspberry Pi 4 (arm64)
# Reverse proxy Nginx + TLS auto-signé + PostgreSQL + backup cron
# Docker Compose v2 — champ "version:" absent (obsolète)
# Ports 9080/9443 — coexistence avec stack postgres/adminer existante
# ================================================================
services:

  # ── Base de données PostgreSQL ───────────────────────────────
  postgres:
    image: postgres:16-alpine
    container_name: semaphore_db
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backups:/backups
    networks:
      - semaphore_net
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ── Semaphore UI ─────────────────────────────────────────────
  semaphore:
    image: semaphoreui/semaphore:latest
    container_name: semaphore_app
    restart: unless-stopped
    user: "0"                          # root requis pour lire /etc/gitconfig
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      SEMAPHORE_DB_DIALECT: postgres
      SEMAPHORE_DB_HOST: postgres
      SEMAPHORE_DB_PORT: 5432
      SEMAPHORE_DB_USER: ${POSTGRES_USER}
      SEMAPHORE_DB_PASS: ${POSTGRES_PASSWORD}
      SEMAPHORE_DB: ${POSTGRES_DB}
      SEMAPHORE_ADMIN: ${SEMAPHORE_ADMIN}
      SEMAPHORE_ADMIN_PASSWORD: ${SEMAPHORE_ADMIN_PASSWORD}
      SEMAPHORE_ADMIN_NAME: ${SEMAPHORE_ADMIN_NAME}
      SEMAPHORE_ADMIN_EMAIL: ${SEMAPHORE_ADMIN_EMAIL}
      SEMAPHORE_ACCESS_KEY_ENCRYPTION: ${SEMAPHORE_ACCESS_KEY_ENCRYPTION}
      SEMAPHORE_TMP_PATH: /tmp/semaphore
    volumes:
      - semaphore_data:/home/semaphore
      - semaphore_tmp:/tmp/semaphore
      - ${SSH_KEYS_PATH}:/home/semaphore/.ssh:ro
      - /home/user/semaphore/playbooks:/home/semaphore/playbooks
      - ./gitconfig-system:/etc/gitconfig:ro
    networks:
      - semaphore_net
    expose:
      - "3000"

  # ── Nginx — Reverse proxy HTTPS ──────────────────────────────
  nginx:
    image: nginx:alpine
    container_name: semaphore_nginx
    restart: unless-stopped
    depends_on:
      - semaphore
    ports:
      - "9080:80"   # 8080 réservé par adminer sur la stack existante
      - "9443:443"  # aligné sur la convention de ports alternative
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
    networks:
      - semaphore_net

  # ── Backup automatique — dump quotidien 02h00, rétention 7j ──
  backup:
    image: postgres:16-alpine
    container_name: semaphore_backup
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
      PGPASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - ./backups:/backups
      - ./backup/backup.sh:/usr/local/bin/backup.sh:ro
    networks:
      - semaphore_net
    entrypoint: >
      sh -c "
        echo '0 2 * * * /usr/local/bin/backup.sh' | crontab - &&
        crond -f -l 2
      "

# ── Volumes nommés ───────────────────────────────────────────────
volumes:
  postgres_data:
    name: semaphore_postgres_data
  semaphore_data:
    name: semaphore_app_data
  semaphore_tmp:
    name: semaphore_tmp

# ── Réseau isolé ─────────────────────────────────────────────────
networks:
  semaphore_net:
    driver: bridge
    name: semaphore_net
```

---

### 3.3 `nginx/nginx.conf`

> Les directives `listen` internes restent sur `80` et `443` — c'est le mapping hôte dans `docker-compose.yml` qui expose `9080`/`9443`. La redirection HTTP→HTTPS pointe vers le port externe `9443`.

```nginx
events {
    worker_connections 512;
}

http {

    # Resolver DNS interne Docker — résolution dynamique des upstreams
    # Évite l'erreur "host not found in upstream" au démarrage de Nginx
    resolver 127.0.0.11 valid=5s;
    resolver_timeout 5s;

    # Redirection HTTP → HTTPS (port externe 9443)
    server {
        listen 80;
        server_name _;
        return 301 https://$host:9443$request_uri;
    }

    # Reverse proxy HTTPS → Semaphore :3000
    server {
        listen 443 ssl;
        server_name _;

        ssl_certificate     /etc/nginx/ssl/semaphore.crt;
        ssl_certificate_key /etc/nginx/ssl/semaphore.key;

        ssl_protocols       TLSv1.2 TLSv1.3;
        ssl_ciphers         HIGH:!aNULL:!MD5;
        ssl_session_cache   shared:SSL:10m;
        ssl_session_timeout 10m;

        # En-têtes de sécurité
        add_header Strict-Transport-Security "max-age=31536000" always;
        add_header X-Frame-Options SAMEORIGIN;
        add_header X-Content-Type-Options nosniff;

        # Limite upload (playbooks, inventaires)
        client_max_body_size 50M;

        location / {
            # Variable obligatoire pour forcer la résolution DNS dynamique
            # Sans cette variable, Nginx résout "semaphore" au démarrage
            # et échoue si le container n'est pas encore prêt (erreur 502)
            set $upstream http://semaphore:3000;
            proxy_pass $upstream;

            proxy_http_version 1.1;
            proxy_set_header Host              $host;
            proxy_set_header X-Real-IP         $remote_addr;
            proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # WebSocket — requis pour les logs temps réel
            proxy_set_header Upgrade           $http_upgrade;
            proxy_set_header Connection        "upgrade";

            proxy_read_timeout 300s;
            proxy_send_timeout 300s;
        }
    }
}
```

---

### 3.4 `scripts/gen-cert.sh`

```bash
#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# Génération d'un certificat TLS auto-signé (SAN) pour Semaphore
# Usage : bash scripts/gen-cert.sh
# ──────────────────────────────────────────────────────────────

set -euo pipefail

source "$(dirname "$0")/../.env"

CERT_DIR="$(dirname "$0")/../nginx/ssl"
mkdir -p "$CERT_DIR"

CN="${SERVER_CN:-semaphore.lan}"
IP="${SERVER_IP:-192.168.1.1}"
DAYS=3650

echo "[INFO] Génération certificat → CN=${CN} | IP=${IP} | validité=${DAYS}j"

cat > /tmp/semaphore_san.cnf <<EOF
[req]
default_bits       = 2048
prompt             = no
default_md         = sha256
distinguished_name = dn
x509_extensions    = v3_req

[dn]
C  = FR
ST = Local
L  = LAN
O  = HomeLab
CN = ${CN}

[v3_req]
subjectAltName   = @alt_names
keyUsage         = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth

[alt_names]
DNS.1 = ${CN}
DNS.2 = localhost
IP.1  = ${IP}
IP.2  = 127.0.0.1
EOF

openssl req -x509 -nodes \
  -newkey rsa:2048 \
  -keyout "${CERT_DIR}/semaphore.key" \
  -out    "${CERT_DIR}/semaphore.crt" \
  -days   ${DAYS} \
  -config /tmp/semaphore_san.cnf

chmod 600 "${CERT_DIR}/semaphore.key"
chmod 644 "${CERT_DIR}/semaphore.crt"

echo "[OK] Certificats générés dans ${CERT_DIR}/"
echo ""
echo "[INFO] Pour faire confiance au certificat (clients Linux) :"
echo "  sudo cp ${CERT_DIR}/semaphore.crt /usr/local/share/ca-certificates/semaphore-lan.crt"
echo "  sudo update-ca-certificates"
```

---

### 3.5 `backup/backup.sh`

> ⚠️ **Le script doit être rendu exécutable sur l'hôte avant le premier démarrage.** Le container monte ce fichier en `:ro` — tout `chmod` à l'intérieur du container échoue avec `Read-only file system`.

```bash
#!/bin/sh
# ──────────────────────────────────────────────────────────────
# Backup quotidien PostgreSQL — rétention 7 jours
# Exécuté par crond dans le container semaphore_backup (02h00)
# Variables injectées via environment du service Docker
# ──────────────────────────────────────────────────────────────

BACKUP_FILE="/backups/semaphore_$(date +%Y%m%d_%H%M).sql.gz"
pg_dump -h postgres -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$BACKUP_FILE"
find /backups -name "*.sql.gz" -mtime +7 -delete
```

Rendre exécutable **sur l'hôte** avant le premier démarrage :

```bash
chmod +x /home/user/semaphore/backup/backup.sh
```

---

### 3.6 `gitconfig-system`

Ce fichier est monté sur `/etc/gitconfig` dans le container. Il est lu par tous les processus Git sans exception, y compris les sous-processus lancés par Semaphore lors de l'exécution des tâches. Il résout l'erreur `fatal: detected dubious ownership` qui survient lorsque le répertoire `playbooks` appartient à un UID différent de l'utilisateur courant du container.

```bash
cat > /home/user/semaphore/gitconfig-system <<'EOF'
[safe]
  directory = *
EOF
```

> ⚠️ L'indentation utilise une **tabulation**, pas des espaces — Git est strict sur ce point.

---

## 4. Procédure de déploiement

```bash
# ── Étape 1 : Créer la structure ────────────────────────────────
mkdir -p /home/user/semaphore/{nginx/ssl,scripts,backup,backups,ssh_keys,playbooks}
cd /home/user/semaphore

# ── Étape 2 : Créer tous les fichiers ───────────────────────────
#   .env · docker-compose.yml · nginx/nginx.conf
#   scripts/gen-cert.sh · backup/backup.sh · gitconfig-system
#   (copier les contenus de ce document)

# ── Étape 3 : Rendre les scripts exécutables ────────────────────
chmod +x scripts/gen-cert.sh
chmod +x backup/backup.sh        # obligatoire — monté :ro dans le container

# ── Étape 4 : Générer le certificat TLS ─────────────────────────
bash scripts/gen-cert.sh

# ── Étape 5 : Générer la clé de chiffrement Semaphore ───────────
openssl rand -base64 32
# → Coller la valeur dans .env → SEMAPHORE_ACCESS_KEY_ENCRYPTION

# ── Étape 6 : Générer les clés SSH Ansible ──────────────────────
# (voir section 5)

# ── Étape 7 : Initialiser le repository Git des playbooks ───────
cd /home/user/semaphore/playbooks
sudo git init && sudo git checkout -b main
sudo git config --global user.email "semaphore@lan"
sudo git config --global user.name "Semaphore"
sudo touch .gitkeep
sudo git add .gitkeep
sudo git commit -m "Initial commit"

# Ownership UID 1001 = utilisateur semaphore dans le container
sudo chown -R 1001:0 /home/user/semaphore/playbooks
cd /home/user/semaphore

# ── Étape 8 : Démarrer la stack ─────────────────────────────────
docker compose up -d

# ── Étape 9 : Vérifier le démarrage ─────────────────────────────
docker compose ps
docker compose logs -f semaphore

# ── Étape 10 : Accéder à l'interface ────────────────────────────
# https://10.0.0.20:9443
# Login : admin / valeur de SEMAPHORE_ADMIN_PASSWORD
```

> **Ports rootless** : pour utiliser les ports standard `80`/`443` :  
> `echo "net.ipv4.ip_unprivileged_port_start=80" | sudo tee -a /etc/sysctl.conf && sudo sysctl -p`  
> Puis remplacer `9080:80` → `80:80` et `9443:443` → `443:443` dans `docker-compose.yml`, et mettre à jour la redirection dans `nginx.conf` (`return 301 https://$host$request_uri`).

---

## 5. Configuration SSH Ansible

Semaphore exécute les scripts et playbooks via SSH. Une paire de clés dédiée doit être générée sur le Pi hôte et la clé publique déployée sur chaque nœud cible.

### 5.1 Génération de la paire de clés

```bash
# Sur le Raspberry Pi 4 — utilisateur user
chmod 700 /home/user/semaphore/ssh_keys

ssh-keygen -t ed25519 -C "semaphore@lan" \
  -f /home/user/semaphore/ssh_keys/semaphore_ansible \
  -N ""

chmod 600 /home/user/semaphore/ssh_keys/semaphore_ansible
chmod 644 /home/user/semaphore/ssh_keys/semaphore_ansible.pub
```

### 5.2 Distribution sur les nœuds cibles

La clé publique doit être déposée sur **chaque nœud** que Semaphore devra piloter.

```bash
# Exemple : nœud Raspberry Pi à 10.0.0.100, user pi
ssh-copy-id -i /home/user/semaphore/ssh_keys/semaphore_ansible.pub pi@10.0.0.100

# Répéter pour chaque nœud supplémentaire
ssh-copy-id -i /home/user/semaphore/ssh_keys/semaphore_ansible.pub pi@10.0.0.101
ssh-copy-id -i /home/user/semaphore/ssh_keys/semaphore_ansible.pub ubuntu@10.0.0.50
```

> Si `ssh-copy-id` n'est pas disponible :
> ```bash
> cat /home/user/semaphore/ssh_keys/semaphore_ansible.pub | \
>   ssh pi@10.0.0.100 "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
> ```

### 5.3 Vérification de l'accès SSH

Tester la connexion **depuis le Pi hôte** avant de configurer Semaphore :

```bash
ssh -i /home/user/semaphore/ssh_keys/semaphore_ansible \
    -o StrictHostKeyChecking=no \
    pi@10.0.0.100 "echo 'SSH OK'"
```

La réponse `SSH OK` confirme que la clé est correctement déployée.

Si `sudo` est requis sur le nœud distant sans mot de passe, ajouter une règle sudoers sur le nœud cible :

```bash
# Sur 10.0.0.100
echo "pi ALL=(ALL) NOPASSWD: /usr/bin/apt, /usr/bin/apt-get" \
  | sudo tee /etc/sudoers.d/semaphore-apt
sudo chmod 440 /etc/sudoers.d/semaphore-apt
```

---

## 6. Gestion des playbooks et scripts

### 6.1 Contraintes d'ownership

Le répertoire `playbooks` monté depuis l'hôte doit appartenir à **UID 1001** (utilisateur `semaphore` dans le container). Les opérations Git sont effectuées avec `sudo` — root ignore la vérification d'ownership Git, ce qui évite l'erreur `dubious ownership` sans configuration supplémentaire.

```bash
# Vérifier l'ownership
ls -la /home/user/semaphore/playbooks/

# Réinitialiser si nécessaire
sudo chown -R 1001:0 /home/user/semaphore/playbooks
```

### 6.2 Procédure de commit

Toute modification de script ou de playbook doit être commitée — Semaphore effectue un `git pull` avant chaque exécution de tâche.

**Bloc à exécuter après chaque modification :**

```bash
cd /home/user/semaphore/playbooks
sudo git add -A
sudo git commit -m "Description du changement"
sudo chown -R 1001:0 /home/user/semaphore/playbooks
```

> ⚠️ Sans ce commit, Semaphore exécute l'ancienne version du script.  
> Le `sudo chown` final est nécessaire car `sudo git` recrée certains fichiers `.git/` avec l'ownership root.

### 6.3 Exemple — script APT check

Ce script se connecte en SSH sur un nœud distant et liste les paquets disponibles à la mise à jour.

`cd /home/user/semaphore/playbooks && sudo vi apt_check.sh`

```bash
#!/bin/bash
# ──────────────────────────────────────────────────────────────
# APT Check — liste les paquets upgradables sur un nœud distant
# Nœud cible : pi@10.0.0.100
# Clé SSH    : /home/semaphore/.ssh/semaphore_ansible
# ──────────────────────────────────────────────────────────────
ssh -i /home/semaphore/.ssh/semaphore_ansible \
    -o StrictHostKeyChecking=no \
    -o BatchMode=yes \
    pi@10.0.0.100 \
    "sudo apt update 2>&1 && echo '--- Paquets upgradables ---' && apt list --upgradable 2>/dev/null"
```

Commiter :

```bash
cd /home/user/semaphore/playbooks
sudo git add apt_check.sh
sudo git commit -m "Add apt_check script for pi@10.0.0.100"
sudo chown -R 1001:0 /home/user/semaphore/playbooks
```

Points critiques :

- Le chemin de la clé SSH est **absolu** : `/home/semaphore/.ssh/semaphore_ansible` — ne jamais utiliser `~` car Semaphore exécute le script avec un `HOME` variable selon le sous-processus
- `StrictHostKeyChecking=no` est acceptable en LAN privé — à durcir en environnement exposé
- `BatchMode=yes` désactive toute invite interactive — le script échoue proprement si la clé n'est pas acceptée

---

## 7. Configuration dans Semaphore UI

L'ordre de création est strict — chaque élément dépend du précédent.

```
Key Store → Inventory → Variable Groups → Repository → Task Template
```

### 7.1 Key Store

**Key Store** → **New Key**

```
Name : ansible-lan
Type : SSH Key
```

Coller le contenu de la clé privée :

```bash
cat /home/user/semaphore/ssh_keys/semaphore_ansible
```

---

### 7.2 Inventory

**Inventory** → **New Inventory**

```
Name              : pi-100
User Credentials  : ansible-lan
Sudo Credentials  : (laisser vide)
Type              : Static
```

Contenu de l'inventaire (champ affiché après sélection du type Static) :

```ini
[target]
pi-100 ansible_host=10.0.0.100 ansible_user=pi
```

Pour plusieurs nœuds :

```ini
[raspberrypis]
rpi-01 ansible_host=10.0.0.100 ansible_user=pi
rpi-02 ansible_host=10.0.0.101 ansible_user=pi

[servers]
srv-01 ansible_host=10.0.0.50 ansible_user=ubuntu

[all:vars]
ansible_ssh_private_key_file=/home/semaphore/.ssh/semaphore_ansible
ansible_python_interpreter=/usr/bin/python3
```

---

### 7.3 Variable Groups

> Dans Semaphore v2.x, **"Environment" a été renommé "Variable Groups"**. C'est le même concept — un groupe vide suffit pour les templates sans variables spécifiques.

**Variable Groups** → **New Variable Group**

```
Name : Default
```

Laisser tous les champs vides → **Save**.

---

### 7.4 Repository

**Repositories** → **New Repository**

```
Name   : Playbooks locaux
URL    : file:///home/semaphore/playbooks
Branch : main
Key    : None
```

> ⚠️ L'URL doit comporter **trois slashes** après `file:` — `file:///home/...`  
> Deux slashes (`file://`) produit l'erreur `Failed updating repository: exit status 128`.

---

### 7.5 Task Template — Bash Script

**Task Templates** → **New Template** → sélectionner **Bash Script**

| Champ | Valeur |
|---|---|
| Name | APT check — pi@10.0.0.100 |
| Script Filename | `apt_check.sh` |
| Repository | Playbooks locaux |
| Inventory | pi-100 |
| Variable Group | Default |

Après avoir sélectionné le repository, cliquer **Set branch** → sélectionner `main` → **Create**.

**Exécution** : **Task Templates** → *(ton template)* → **Run**

Les sorties s'affichent en temps réel dans le terminal intégré. Exemple de sortie attendue :

```
Hit:1 http://archive.raspberrypi.org/debian bookworm InRelease
Hit:2 http://deb.debian.org/debian bookworm InRelease
...
Reading package lists... Done
--- Paquets upgradables ---
Listing... Done
curl/bookworm 7.88.1-10+deb12u8 arm64 [upgradable from: 7.88.1-10+deb12u5]
openssh-client/bookworm 1:9.2p1-2+deb12u3 arm64 [upgradable from: ...]
```

---

## 8. Gestion des sauvegardes

Les dumps sont produits automatiquement chaque nuit à **02h00** par le container `semaphore_backup`, avec une rétention de **7 jours**.

### Dump manuel immédiat

```bash
docker exec semaphore_db pg_dump \
  -U semaphore semaphore \
  | gzip > /home/user/semaphore/backups/semaphore_manual_$(date +%Y%m%d_%H%M).sql.gz
```

### Restauration

```bash
# Lister les sauvegardes disponibles
ls -lh /home/user/semaphore/backups/

# Restaurer un dump
gunzip -c /home/user/semaphore/backups/semaphore_YYYYMMDD_HHMM.sql.gz \
  | docker exec -i semaphore_db psql -U semaphore semaphore
```

### Vérification du cron de backup

```bash
docker exec semaphore_backup crontab -l
docker logs semaphore_backup --tail 20
```

---

## 9. Confiance au certificat TLS

Le certificat auto-signé inclut les **Subject Alternative Names (SAN)** pour l'IP LAN et le hostname, le rendant compatible avec les navigateurs modernes une fois importé.

### Linux (clients sur le LAN)

```bash
scp user@10.0.0.20:/home/user/semaphore/nginx/ssl/semaphore.crt /tmp/
sudo cp /tmp/semaphore.crt /usr/local/share/ca-certificates/semaphore-lan.crt
sudo update-ca-certificates
```

### Firefox

**Paramètres** → **Vie privée et sécurité** → **Certificats** → **Afficher les certificats** → onglet **Autorités** → **Importer** → sélectionner `semaphore.crt`

### Chrome / Chromium

**Paramètres** → **Confidentialité** → **Gérer les certificats** → **Autorités** → **Importer**

---

## 10. Commandes d'exploitation

```bash
# ── Cycle de vie ─────────────────────────────────────────────────
docker compose up -d           # Démarrer
docker compose down            # Arrêter (volumes conservés)
docker compose restart         # Redémarrer tous les services
docker compose restart nginx   # Redémarrer uniquement Nginx

# ── Logs ─────────────────────────────────────────────────────────
docker compose logs -f                  # Tous les services
docker compose logs -f semaphore        # Semaphore uniquement
docker compose logs -f nginx --tail 50  # 50 dernières lignes Nginx

# ── État et ressources ───────────────────────────────────────────
docker compose ps
docker stats --no-stream

# ── Vérification réseau ──────────────────────────────────────────
docker network inspect semaphore_net
docker network ls | grep semaphore

# ── Mise à jour de l'image Semaphore ────────────────────────────
docker compose pull semaphore
docker compose up -d semaphore

# ── Accès shell ──────────────────────────────────────────────────
docker exec -it semaphore_app  sh
docker exec -it semaphore_db   psql -U semaphore semaphore
docker exec -it semaphore_nginx sh

# ── Vérification Git dans le container ──────────────────────────
docker exec semaphore_app cat /etc/gitconfig
docker exec semaphore_app git -C /home/semaphore/playbooks status
```

> Interface web : **https://10.0.0.20:9443** · Login : `admin` / valeur de `SEMAPHORE_ADMIN_PASSWORD`

---

## 11. Création de tâches Ansible

Pour des tâches multi-nœuds récurrentes, utiliser un playbook Ansible plutôt qu'un script Bash.

### Playbook `apt_upgrade.yml`

`cd /home/user/semaphore/playbooks && sudo vi apt_upgrade.yml`

```yaml
---
- name: APT Update & Upgrade
  hosts: all
  become: true

  tasks:
    - name: Mettre à jour le cache APT
      ansible.builtin.apt:
        update_cache: true
        cache_valid_time: 3600

    - name: Upgrader tous les paquets
      ansible.builtin.apt:
        upgrade: dist
        autoremove: true
        autoclean: true

    - name: Vérifier si un reboot est nécessaire
      ansible.builtin.stat:
        path: /var/run/reboot-required
      register: reboot_required

    - name: Afficher l'état reboot
      ansible.builtin.debug:
        msg: "Reboot requis sur {{ inventory_hostname }}"
      when: reboot_required.stat.exists
```

```bash
cd /home/user/semaphore/playbooks
sudo git add apt_upgrade.yml
sudo git commit -m "Add apt_upgrade playbook"
sudo chown -R 1001:0 /home/user/semaphore/playbooks
```

### Task Template Ansible

**Task Templates** → **New Template** → sélectionner **Ansible Playbook**

| Champ | Valeur |
|---|---|
| Name | APT Upgrade — Tous les nœuds |
| Playbook Filename | `apt_upgrade.yml` |
| Repository | Playbooks locaux |
| Inventory | pi-100 |
| Variable Group | Default |

### Planification (Schedule)

**Task Templates** → *(ton template)* → **Schedules** → **New Schedule**

```
# Tous les dimanches à 03h00
0 3 * * 0

# Tous les jours à 03h00
0 3 * * *

# Le 1er du mois à 02h00
0 2 1 * *
```

Référence rapide :
```
┌─ minute (0-59)
│  ┌─ heure (0-23)
│  │  ┌─ jour du mois (1-31)
│  │  │  ┌─ mois (1-12)
│  │  │  │  ┌─ jour semaine (0=dim, 7=dim)
0  3  *  *  0
```

### Bash vs Ansible — choix rapide

| Besoin | Choix |
|---|---|
| Commande one-shot, sortie brute | **Bash Script** |
| Vérification rapide sur un nœud | **Bash Script** |
| Tâche récurrente multi-nœuds | **Ansible Playbook** |
| `apt upgrade`, déploiements, configs | **Ansible Playbook** |

---

## 12. Coexistence avec d'autres stacks Docker

| Port hôte | Service concurrent | Service Semaphore | Résolution |
|---|---|---|---|
| `8080` | adminer | nginx (HTTP) | nginx mappé sur `9080:80` |
| `5432` | postgres existant | `semaphore_db` (non exposé) | aucun conflit |

`semaphore_db` n'expose aucun port hôte — il est uniquement accessible via `semaphore_net`. Aucune collision avec un postgres existant sur le même hôte.

```bash
# Identifier les ports occupés sur l'hôte
docker ps --format "table {{.Names}}\t{{.Ports}}"
ss -tlnp | grep -E ':(80|443|8080|8443|9080|9443|5432)'
```

> ⚠️ Si le réseau apparaît avec un préfixe inattendu (ex. `semaphore_semaphore_net`), c'est que le champ `name:` est absent de la section `networks:` dans le compose. Le champ `name: semaphore_net` est obligatoire pour figer le nom sans préfixe de projet. En cas de doublon, supprimer l'orphelin :
> ```bash
> docker network rm semaphore_semaphore_net
> ```

---

## 13. Sécurité et recommandations

| Point | Action recommandée |
|---|---|
| **Mots de passe** | Utiliser `openssl rand -base64 24` pour tous les secrets `.env` |
| **Clé de chiffrement** | Ne jamais modifier `SEMAPHORE_ACCESS_KEY_ENCRYPTION` après le premier démarrage — invalide toutes les clés stockées |
| **Accès réseau** | Limiter les ports 9080/9443 au VLAN de management |
| **Firewall** | `sudo ufw allow from 10.0.0.0/24 to any port 9443` |
| **Mises à jour** | `docker compose pull && docker compose up -d` via cron mensuel |
| **Rotation du certificat** | Valide 10 ans — re-générer si l'IP LAN change |
| **Clés SSH** | Une clé dédiée par environnement (dev/prod) — ne pas réutiliser les clés personnelles |
| **sudoers nœuds** | Limiter `NOPASSWD` aux seules commandes nécessaires (`apt`, `apt-get`) |
| **Backups** | Tester la restauration périodiquement — envisager un rsync vers un NAS externe |
| **`user: "0"`** | Le container semaphore tourne en root pour résoudre les contraintes Git — acceptable en LAN privé, à réévaluer si exposition publique |

---

*Document mis à jour le 2026-03-17 — Stack Semaphore UI v2.17.x · arm64 · user@10.0.0.20*
