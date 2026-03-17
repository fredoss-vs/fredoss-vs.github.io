# Ansible avec Semaphore UI — Playbooks et scripts avancés

> **Stack** : Semaphore UI v2.17.x · Ansible 2.14+ · Raspberry Pi 4 (arm64)  
> **Hôte** : `derf@10.0.0.20` · Playbooks : `/home/derf/semaphore/playbooks`  
> **Révision** : 2026-03-17

---

## Table des matières

- [Ansible avec Semaphore UI — Playbooks et scripts avancés](#ansible-avec-semaphore-ui--playbooks-et-scripts-avancés)
  - [Table des matières](#table-des-matières)
  - [1. Bash vs Ansible — quand choisir quoi](#1-bash-vs-ansible--quand-choisir-quoi)
  - [2. Règles fondamentales Ansible dans Semaphore](#2-règles-fondamentales-ansible-dans-semaphore)
  - [3. Script Bash robuste — SSH multi-lignes](#3-script-bash-robuste--ssh-multi-lignes)
    - [3.1 Script APT maintenance — nœud unique](#31-script-apt-maintenance--nœud-unique)
    - [3.2 Variante multi-machines](#32-variante-multi-machines)
  - [4. Playbooks Ansible — maintenance APT](#4-playbooks-ansible--maintenance-apt)
    - [4.1 Version simple](#41-version-simple)
    - [4.2 Version robuste avec assertion OS](#42-version-robuste-avec-assertion-os)
    - [4.3 Version avec dist-upgrade](#43-version-avec-dist-upgrade)
    - [4.4 Version avec tags — recommandée pour Semaphore](#44-version-avec-tags--recommandée-pour-semaphore)
  - [5. Inventory Ansible](#5-inventory-ansible)
    - [Nœud unique](#nœud-unique)
    - [Multi-nœuds avec groupes](#multi-nœuds-avec-groupes)
  - [6. Déploiement dans Semaphore UI](#6-déploiement-dans-semaphore-ui)
    - [6.1 Procédure de commit](#61-procédure-de-commit)
    - [6.2 Création des Task Templates](#62-création-des-task-templates)
    - [6.3 Exécution par tag](#63-exécution-par-tag)
  - [7. Bonnes pratiques](#7-bonnes-pratiques)

---

## 1. Bash vs Ansible — quand choisir quoi

| Besoin | Choix | Raison |
|---|---|---|
| Vérification rapide, sortie brute | **Bash** | Résultat immédiat, pas de dépendance |
| `apt list --upgradable` en one-shot | **Bash** | Lecture seule, pas d'état à gérer |
| `apt upgrade` sur plusieurs nœuds | **Ansible** | Idempotent, logs structurés, rollback |
| Déploiement de configuration | **Ansible** | Gestion d'état, modules dédiés |
| Tâche planifiée récurrente | **Ansible** | Meilleure gestion des erreurs par nœud |
| Test rapide sans infrastructure | **Bash** | Pas de repo Git requis |

**Règle principale** : dès qu'une tâche implique plusieurs nœuds, de l'état système, ou une planification récurrente, Ansible est la bonne réponse. Bash dépanne, Ansible industrialise.

---

## 2. Règles fondamentales Ansible dans Semaphore

- Utiliser `become: true` au niveau du play plutôt que `sudo` dans les commandes `shell` ou `command`
- Éviter `shell` ou `command` pour des actions APT — le module `ansible.builtin.apt` existe précisément pour ça
- Garder `gather_facts: true` pour filtrer les hôtes par OS et accéder aux variables système
- Utiliser `DEBIAN_FRONTEND=noninteractive` via la variable d'environnement Ansible pour éviter les prompts interactifs bloquants
- Séparer les tâches avec des `tags` pour une exécution granulaire dans Semaphore
- Ne jamais coder IP, utilisateur ou chemin de clé SSH directement dans un playbook — tout doit passer par l'inventory

Dans le module `apt` :

| Valeur | Comportement |
|---|---|
| `upgrade: true` | Upgrade standard — ne change pas les dépendances |
| `upgrade: dist` | Équivalent `dist-upgrade` / `full-upgrade` — accepte les changements de dépendances |

Recommandation : `upgrade: true` pour les serveurs de production, `upgrade: dist` pour les machines de laboratoire ou moins sensibles.

---

## 3. Script Bash robuste — SSH multi-lignes

Le script Bash reste pertinent pour des vérifications ponctuelles ou des one-shots. La version ci-dessous est structurée avec un bloc SSH heredoc pour la lisibilité et la maintenabilité.

### 3.1 Script APT maintenance — nœud unique

`cd /home/derf/semaphore/playbooks && sudo vi apt_maintenance.sh`

```bash
#!/bin/bash
# ============================================================
# Script  : apt_maintenance.sh
# Objectif : Maintenance APT distante via SSH
# Cible   : Raspberry Pi / Debian / Ubuntu
# Usage   : Bash Script dans Semaphore UI
# ============================================================

# ── Configuration ────────────────────────────────────────────
SSH_KEY="/home/semaphore/.ssh/semaphore_ansible"
REMOTE_USER="pi"
REMOTE_HOST="10.0.0.100"

# ── Exécution ────────────────────────────────────────────────
ssh -i "$SSH_KEY" \
    -o StrictHostKeyChecking=no \
    -o BatchMode=yes \
    ${REMOTE_USER}@${REMOTE_HOST} << 'EOF'

echo "=============================="
echo "Debut maintenance systeme"
echo "=============================="

echo "[1/4] apt update"
sudo apt update -y

echo "------------------------------"
echo "Paquets upgradables :"
apt list --upgradable 2>/dev/null

echo "------------------------------"
echo "[2/4] apt upgrade"
sudo DEBIAN_FRONTEND=noninteractive apt upgrade -y

echo "------------------------------"
echo "[3/4] apt autoremove"
sudo apt autoremove -y

echo "[4/4] apt autoclean"
sudo apt autoclean

echo "=============================="
echo "Maintenance terminee"
echo "=============================="

EOF
```

**Pourquoi ce format est préférable à une guirlande de `&&` :**

- Bloc SSH heredoc → lisible et maintenable
- `DEBIAN_FRONTEND=noninteractive` → évite les prompts interactifs bloquants à 02h00
- Logs structurés → sortie lisible dans le terminal Semaphore
- Ordre logique : `update` → `upgrade` → `autoremove` → `autoclean`

### 3.2 Variante multi-machines

`cd /home/derf/semaphore/playbooks && sudo vi apt_maintenance_multi.sh`

```bash
#!/bin/bash
# ============================================================
# Script  : apt_maintenance_multi.sh
# Objectif : Maintenance APT sur plusieurs nœuds en séquence
# ============================================================

SSH_KEY="/home/semaphore/.ssh/semaphore_ansible"
REMOTE_USER="pi"
HOSTS=("10.0.0.100" "10.0.0.101" "10.0.0.102")

for HOST in "${HOSTS[@]}"; do
    echo ""
    echo "===== Traitement : ${HOST} ====="

    ssh -i "$SSH_KEY" \
        -o StrictHostKeyChecking=no \
        -o BatchMode=yes \
        ${REMOTE_USER}@${HOST} 'bash -s' << 'EOF'

sudo apt update -y
sudo DEBIAN_FRONTEND=noninteractive apt upgrade -y
sudo apt autoremove -y
sudo apt autoclean

EOF

    if [ $? -eq 0 ]; then
        echo "===== OK : ${HOST} ====="
    else
        echo "===== ERREUR : ${HOST} — vérifier la connexion SSH ====="
    fi

done
```

---

## 4. Playbooks Ansible — maintenance APT

### 4.1 Version simple

Suffisante pour les cas standards sans besoin de debug fin.

`cd /home/derf/semaphore/playbooks && sudo vi apt_simple.yml`

```yaml
---
- name: Maintenance APT simple
  hosts: all
  become: true

  tasks:
    - name: Update + upgrade + autoremove + autoclean
      ansible.builtin.apt:
        update_cache: true
        upgrade: true
        autoremove: true
        autoclean: true
```

### 4.2 Version robuste avec assertion OS

Vérifie la compatibilité de l'OS avant d'exécuter, affiche les paquets upgradables et fournit un résumé détaillé.

`cd /home/derf/semaphore/playbooks && sudo vi apt_maintenance.yml`

```yaml
---
- name: Maintenance système Debian/Ubuntu
  hosts: all
  become: true
  gather_facts: true

  vars:
    apt_cache_valid_time: 3600

  tasks:
    - name: Vérifier que l'OS est bien Debian/Ubuntu
      ansible.builtin.assert:
        that:
          - ansible_os_family == "Debian"
        fail_msg: "Ce playbook ne supporte que Debian/Ubuntu."
        success_msg: "OS compatible : {{ ansible_distribution }} {{ ansible_distribution_version }}"

    - name: Mettre à jour le cache APT
      ansible.builtin.apt:
        update_cache: true
        cache_valid_time: "{{ apt_cache_valid_time }}"

    - name: Lister les paquets upgradables
      ansible.builtin.command: apt list --upgradable
      register: apt_upgradable
      changed_when: false
      failed_when: false

    - name: Afficher les paquets upgradables
      ansible.builtin.debug:
        msg: "{{ apt_upgradable.stdout_lines | default(['Aucun paquet détecté']) }}"

    - name: Appliquer les mises à jour
      ansible.builtin.apt:
        upgrade: true
        autoremove: true
        autoclean: true
      register: apt_result

    - name: Résumé de la maintenance
      ansible.builtin.debug:
        var: apt_result

    - name: Vérifier si un reboot est nécessaire
      ansible.builtin.stat:
        path: /var/run/reboot-required
      register: reboot_required

    - name: Signaler si un reboot est requis
      ansible.builtin.debug:
        msg: "ATTENTION — Reboot requis sur {{ inventory_hostname }}"
      when: reboot_required.stat.exists
```

### 4.3 Version avec dist-upgrade

Pour les machines de laboratoire ou les mises à jour majeures acceptant les changements de dépendances.

`cd /home/derf/semaphore/playbooks && sudo vi apt_dist_upgrade.yml`

```yaml
---
- name: Maintenance système — dist-upgrade
  hosts: all
  become: true
  gather_facts: true

  tasks:
    - name: Vérifier que l'OS est bien Debian/Ubuntu
      ansible.builtin.assert:
        that:
          - ansible_os_family == "Debian"
        fail_msg: "Ce playbook ne supporte que Debian/Ubuntu."

    - name: Update cache + dist-upgrade + nettoyage complet
      ansible.builtin.apt:
        update_cache: true
        upgrade: dist
        autoremove: true
        autoclean: true
      register: apt_result

    - name: Résumé
      ansible.builtin.debug:
        var: apt_result

    - name: Vérifier si un reboot est nécessaire
      ansible.builtin.stat:
        path: /var/run/reboot-required
      register: reboot_required

    - name: Signaler si un reboot est requis
      ansible.builtin.debug:
        msg: "ATTENTION — Reboot requis sur {{ inventory_hostname }}"
      when: reboot_required.stat.exists
```

### 4.4 Version avec tags — recommandée pour Semaphore

Permet de créer des Task Templates distincts dans Semaphore pour chaque phase de la maintenance, ou d'exécuter toutes les phases en une seule passe avec `--tags apt`.

`cd /home/derf/semaphore/playbooks && sudo vi apt_tagged.yml`

```yaml
---
- name: Maintenance APT avec tags
  hosts: all
  become: true
  gather_facts: true

  tasks:
    - name: Vérifier que l'OS est bien Debian/Ubuntu
      ansible.builtin.assert:
        that:
          - ansible_os_family == "Debian"
        fail_msg: "Ce playbook ne supporte que Debian/Ubuntu."
      tags:
        - always

    - name: Mettre à jour le cache APT
      ansible.builtin.apt:
        update_cache: true
        cache_valid_time: 3600
      tags:
        - update
        - apt

    - name: Lister les paquets upgradables
      ansible.builtin.command: apt list --upgradable
      register: apt_upgradable
      changed_when: false
      failed_when: false
      tags:
        - update
        - apt

    - name: Afficher les paquets upgradables
      ansible.builtin.debug:
        msg: "{{ apt_upgradable.stdout_lines | default(['Aucun paquet détecté']) }}"
      tags:
        - update
        - apt

    - name: Appliquer les mises à jour
      ansible.builtin.apt:
        upgrade: true
      tags:
        - upgrade
        - apt

    - name: Supprimer les paquets inutiles
      ansible.builtin.apt:
        autoremove: true
      tags:
        - autoremove
        - apt

    - name: Nettoyer le cache APT
      ansible.builtin.apt:
        autoclean: true
      tags:
        - autoclean
        - apt

    - name: Vérifier si un reboot est nécessaire
      ansible.builtin.stat:
        path: /var/run/reboot-required
      register: reboot_required
      tags:
        - upgrade
        - apt

    - name: Signaler si un reboot est requis
      ansible.builtin.debug:
        msg: "ATTENTION — Reboot requis sur {{ inventory_hostname }}"
      when: reboot_required.stat.exists
      tags:
        - upgrade
        - apt
```

> Le tag `always` sur l'assertion OS garantit qu'elle est toujours exécutée, quel que soit le tag passé à Semaphore.

---

## 5. Inventory Ansible

L'inventory est défini directement dans Semaphore UI (type Static) — ne pas le versionner dans le repo Git.

### Nœud unique

```ini
[raspberry]
rpi-01 ansible_host=10.0.0.100 ansible_user=pi

[raspberry:vars]
ansible_ssh_private_key_file=/home/semaphore/.ssh/semaphore_ansible
ansible_ssh_common_args='-o StrictHostKeyChecking=no'
ansible_python_interpreter=/usr/bin/python3
```

### Multi-nœuds avec groupes

```ini
[raspberry]
rpi-01 ansible_host=10.0.0.100 ansible_user=pi
rpi-02 ansible_host=10.0.0.101 ansible_user=pi
rpi-03 ansible_host=10.0.0.102 ansible_user=pi

[servers]
srv-01 ansible_host=10.0.0.50  ansible_user=ubuntu
srv-02 ansible_host=10.0.0.51  ansible_user=ubuntu

[all:vars]
ansible_ssh_private_key_file=/home/semaphore/.ssh/semaphore_ansible
ansible_ssh_common_args='-o StrictHostKeyChecking=no'
ansible_python_interpreter=/usr/bin/python3
```

---

## 6. Déploiement dans Semaphore UI

### 6.1 Procédure de commit

Après chaque création ou modification de playbook :

```bash
cd /home/derf/semaphore/playbooks
sudo git add -A
sudo git commit -m "Description du changement"
sudo chown -R 1001:0 /home/derf/semaphore/playbooks
```

> Le `sudo chown` final est nécessaire car `sudo git` recrée certains fichiers `.git/` avec l'ownership root, ce qui bloquerait le `git pull` de Semaphore lors de la prochaine exécution.

### 6.2 Création des Task Templates

L'ordre de création dans Semaphore UI est strict :

```
Key Store → Inventory → Variable Groups → Repository → Task Template
```

**Task Template — version robuste (toutes les phases)**

**Task Templates** → **New Template** → **Ansible Playbook**

| Champ | Valeur |
|---|---|
| Name | APT Maintenance complète |
| Playbook Filename | `apt_maintenance.yml` |
| Repository | Playbooks locaux |
| Inventory | *(ton inventory)* |
| Variable Group | Default |

---

**Task Templates pour la version avec tags — un template par phase**

| Template | Playbook | CLI args |
|---|---|---|
| APT — Update cache | `apt_tagged.yml` | `--tags update` |
| APT — Upgrade paquets | `apt_tagged.yml` | `--tags upgrade` |
| APT — Autoremove | `apt_tagged.yml` | `--tags autoremove` |
| APT — Autoclean | `apt_tagged.yml` | `--tags autoclean` |
| APT — Maintenance complète | `apt_tagged.yml` | `--tags apt` |

Pour chaque template, renseigner le champ **CLI args** avec l'option `--tags` correspondante.

### 6.3 Exécution par tag

Dans Semaphore UI, le champ **CLI args** du Task Template accepte directement les options Ansible :

```
--tags update
--tags upgrade
--tags apt
--tags update,upgrade
--skip-tags autoclean
```

Exemples d'utilisation combinés :

```
# Uniquement le cache update
--tags update

# Update + upgrade sans nettoyage
--tags update,upgrade

# Tout sauf autoclean
--skip-tags autoclean

# Exécution complète
--tags apt
```

---

## 7. Bonnes pratiques

| Règle | Détail |
|---|---|
| **`become: true` au niveau play** | Ne pas utiliser `sudo` dans les commandes `shell` ou `command` |
| **Module `apt` plutôt que `command`** | `ansible.builtin.apt` gère l'idempotence nativement |
| **`gather_facts: true`** | Permet le filtrage par OS (`ansible_os_family`) et l'accès aux variables système |
| **`DEBIAN_FRONTEND=noninteractive`** | Évite les prompts bloquants lors des upgrades interactifs |
| **`cache_valid_time`** | Évite un `apt update` inutile si le cache est récent |
| **`changed_when: false`** sur `apt list`** | `apt list` ne modifie rien — ne pas le marquer comme changed |
| **`failed_when: false`** sur `apt list`** | `apt list` peut retourner des warnings non bloquants |
| **Tags `always`** sur les assertions | Garantit l'exécution des vérifications préalables quel que soit le tag passé |
| **Inventory dans Semaphore** | Ne pas coder IP/user/clé dans les playbooks — tout passe par l'inventory |
| **`upgrade: true` en production** | `upgrade: dist` uniquement sur les machines de labo ou hors production |
| **Vérification reboot** | Toujours vérifier `/var/run/reboot-required` après un upgrade |
| **Chemin SSH absolu** | Toujours `/home/semaphore/.ssh/semaphore_ansible` — jamais `~` dans les scripts |

---

*Document généré le 2026-03-17 — Semaphore UI v2.17.x · Ansible 2.14+ · arm64 · derf@10.0.0.20*
