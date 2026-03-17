#!/bin/bash

# ============================================================
# Script : update_upgrade_autoclean.sh
# Objectif : Mise à jour distante via SSH (apt update/upgrade/autoclean)
# Compatible : Raspberry Pi / Debian / Ubuntu
# ============================================================

# ── CONFIG ───────────────────────────────────────────────────
SSH_KEY="/home/semaphore/.ssh/semaphore_ansible"
REMOTE_USER="xx" # A modifier
REMOTE_HOST="10.0.0.xxx" # A modifier

# ── EXECUTION ────────────────────────────────────────────────
ssh -i "$SSH_KEY" \
    -o StrictHostKeyChecking=no \
    -o BatchMode=yes \
    ${REMOTE_USER}@${REMOTE_HOST} << 'EOF'

echo "=============================="
echo "🚀 Début maintenance système"
echo "=============================="

# Mise à jour des dépôts
echo "[1/4] apt update"
sudo apt update -y

# Liste des paquets upgradables
echo "------------------------------"
echo "📦 Paquets upgradables :"
apt list --upgradable 2>/dev/null

# Upgrade
echo "------------------------------"
echo "[2/4] apt upgrade"
sudo DEBIAN_FRONTEND=noninteractive apt upgrade -y

# Nettoyage
echo "------------------------------"
echo "[3/4] apt autoremove"
sudo apt autoremove -y

echo "[4/4] apt autoclean"
sudo apt autoclean

echo "=============================="
echo "✅ Maintenance terminée"
echo "=============================="

EOF