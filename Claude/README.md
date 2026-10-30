# statusline.sh

Statusline riche pour [Claude Code](https://claude.ai/code) affichant en une ligne : modèle actif, fenêtre de contexte, tokens, delta entre rafraîchissements, niveau d'effort, quotas 5h / 7j, branche git, lignes modifiées et coût de session.

```
✦ Opus 5.5 (1M) ░░░░░░░░ 6% ↓64.2k ↑900 │ Δ ↓0 ↑470 │ ▲▲ xhigh │ 󰥔 5h 40% (0h52m) │ 󰃰 7d 44% (1d02h) │ 󰘬 main ~2 │ +74/-50 │ $0.56
```

![statusline.png](/Claude/statusline.png)

| Segment                      | Source                                                                  | Description                                                      |
| ---------------------------- | ----------------------------------------------------------------------- | ---------------------------------------------------------------- |
| `✦ Opus 5.5`                 | `model.display_name`                                                    | Modèle actif                                                     |
| `(1M)`                       | `context_window.context_window_size`                                    | Taille de la fenêtre de contexte                                 |
| `░░░░░░░░ 6%`                | `context_window.current_usage.*` ÷ taille (repli : `used_percentage`)   | Remplissage du contexte (barre 8 blocs)                          |
| `↓64.2k`                     | `current_usage.input_tokens` + `cache_creation_*` + `cache_read_*`      | Tokens actuellement dans le contexte                             |
| `↑900`                       | `context_window.total_output_tokens`                                    | Tokens générés dans la session                                   |
| `Δ ↓0 ↑470`                  | calculé (fichier cache par session)                                     | Tokens entrée / sortie depuis le dernier changement              |
| `▲▲ xhigh`                   | `effort.level`                                                          | Effort : `▽ low`, `◆ med`, `▲ high`, `▲▲ xhigh`, `⬆ max` (masqué si absent) |
| `󰥔 5h 40% (0h52m)`           | `rate_limits.five_hour` (repli : API `oauth/usage`)                     | Quota 5h consommé + temps avant reset                            |
| `󰃰 7d 44% (1d02h)`           | `rate_limits.seven_day` (repli : API `oauth/usage`)                     | Quota 7j consommé + temps avant reset                            |
| `󰘬 main +2 ~6`               | `git branch` / `git status` dans `cwd`                                  | Branche (tronquée à 20 car., `@sha` si HEAD détaché), fichiers indexés `+`, modifiés `~` |
| `+74/-50`                    | `cost.total_lines_added` / `cost.total_lines_removed`                   | Lignes ajoutées / supprimées dans la session                     |
| `$0.56`                      | `cost.total_cost_usd`                                                   | Coût USD de la session (masqué si nul)                           |

Couleurs (contexte et quotas) : vert < 30 %, orange 30–49 %, jaune 50–79 %, rouge ≥ 80 %.

Les nombres sont toujours affichés avec un point décimal, quelle que soit la locale du système.

### Quotas : stdin puis repli API

Claude Code fournit les quotas sur stdin (`rate_limits.five_hour` / `seven_day`, abonnés Pro/Max, après la première réponse de la session). C'est la source utilisée en priorité.

Si ces champs sont absents, le script interroge `https://api.anthropic.com/api/oauth/usage` avec le jeton OAuth de Claude Code (lu dans le trousseau macOS ou dans `~/.claude/.credentials.json`), avec un cache de **90 s**. Si aucune source ne répond, les segments quotas sont masqués.

> Cet endpoint n'est pas documenté publiquement et peut changer sans préavis. Le jeton n'est envoyé qu'à `api.anthropic.com`.

### Fichiers cache

Stockés dans `$TMPDIR`, ou à défaut `~/.claude/.cache/` :

| Fichier                                  | Rôle                                  | Durée de vie |
| ---------------------------------------- | ------------------------------------- | ------------ |
| `claude-statusline-cache.json`           | Réponse de l'API quotas (repli)       | 90 s         |
| `claude-statusline-delta-<session>.json` | Compteurs pour le calcul du `Δ`       | purgé après 2 jours |
| `gitcache-<hash>`                        | Branche / statut git par répertoire   | 5 s, purgé après 2 jours |

---

## Dépendances

| Outil  | Usage                                   | Obligatoire |
| ------ | --------------------------------------- | ----------- |
| `bash` | interpréteur                            | oui         |
| `jq`   | parsing du JSON reçu sur stdin          | oui         |
| `awk`  | formatage des nombres                   | oui         |
| `curl` | appel de l'API quotas                   | non (repli stdin) |
| `git`  | segment branche                         | non         |

Une [Nerd Font](https://www.nerdfonts.com/) est nécessaire pour les icônes `󰥔`, `󰃰` et `󰘬`.

### Windows

Installer [Git for Windows](https://git-scm.com/download/win) — fournit Git Bash avec `bash`, `awk`, `curl` et `git`. Puis `jq` :

```powershell
winget install jqlang.jq     # recommandé
choco install jq             # Chocolatey
scoop install jq             # Scoop
```

Si `jq` n'est pas dans le PATH de Git Bash, le script cherche aussi `~/.claude/bin/jq`.

### macOS

```bash
brew install jq
```

### Linux

```bash
sudo apt install jq        # Debian/Ubuntu
sudo dnf install jq        # Fedora/RHEL
```

Vérifier : `jq --version`

---

## Installation

### 1. Copier le script

```bash
cp statusline.sh ~/.claude/statusline.sh
chmod +x ~/.claude/statusline.sh
```

### 2. Configurer `~/.claude/settings.json`

Ajouter ou modifier la clé `statusLine` :

```json
{
  "statusLine": {
    "type": "command",
    "command": "bash C:/Users/<VotreNom>/.claude/statusline.sh",
    "refreshInterval": 10
  }
}
```

> **Windows** : utiliser des slashes (`C:/Users/...`) et préfixer avec `bash` — le `~` n'est pas développé par Claude Code sur Windows.
>
> **macOS / Linux** : `"command": "~/.claude/statusline.sh"` suffit.

### 3. Redémarrer Claude Code

La statusline se met à jour à chaque événement de la session, et en plus toutes les `refreshInterval` secondes.

---

## Dépannage

**La statusline n'apparaît pas du tout**

- Vérifier que `bash` est dans le PATH : `where bash` (PowerShell)
- Tester le script à la main :
  ```bash
  echo '{"model":{"display_name":"Test"}}' | bash ~/.claude/statusline.sh
  ```

**Affiché `Claude (jq manquant)`**

- `jq` introuvable dans le PATH de Git Bash ni dans `~/.claude/bin/jq`.

**Icônes `󰥔` `󰃰` `󰘬` affichées comme des carrés**

- Le terminal n'utilise pas de Nerd Font. En installer une, ou remplacer ces caractères dans le script (ex. `⏱`, `📅`, `⎇`).

**Segments quotas `5h` / `7d` absents**

- Ni stdin ni l'API n'ont fourni de données : normal avant la première réponse de la session, ou si vous êtes connecté par clé API (pas d'abonnement Pro/Max).
- Supprimer `claude-statusline-cache.json` pour forcer un nouvel appel API.

**Debug — inspecter le JSON brut reçu**

```bash
# Ajouter temporairement après la ligne `input=$(cat)` :
echo "$input" > "$HOME/statusline-debug.json"
# Puis lire : cat ~/statusline-debug.json
```
