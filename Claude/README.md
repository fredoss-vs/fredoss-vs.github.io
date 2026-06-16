# statusline.sh

Statusline riche pour [Claude Code](https://claude.ai/code) affichant en une ligne : modèle actif, fenêtre de contexte, tokens, niveau d'effort, coût de session et quota rate-limit.

```
✦ Sonnet 4.6 (200k) ██████░░░░ 60% │ Δ 42.6k │ ▲ high │ $0.43 │ 󰥔 5h: 52% 1h30m │ 7d: 19%
```

| Segment                      | Source JSON                               | Description                                 |
| ---------------------------- | ----------------------------------------- | ------------------------------------------- |
| `✦ Sonnet 4.6`            | `model.display_name`                    | Modèle actif                               |
| `(200k)`                   | `context_window.context_window_size`    | Taille de la fenêtre de contexte           |
| `██████░░░░ 60%` | `context_window.used_percentage`        | Utilisation de la fenêtre (barre 10 blocs) |
| `Δ 42.6k`                 | `context_window.total_input_tokens`     | Tokens envoyés dans la session             |
| `▲ high`                  | `effort.level`                          | Niveau de thinking (low / med / high)       |
| `$0.43`                    | `cost.total_cost_usd`                   | Coût USD de la session                     |
| `󰥔 5h: 52%`               | `rate_limits.five_hour.used_percentage` | Quota 5h consommé                          |
| `1h30m`                    | `rate_limits.five_hour.resets_at`       | Temps avant reset du quota 5h               |
| `7d: 19%`                  | `rate_limits.seven_day.used_percentage` | Quota 7j consommé                          |

Couleurs : vert < 70 %, jaune 70–89 %, rouge ≥ 90 % (quota et contexte).

---

## Dépendances

### jq (obligatoire)

`jq` parse le JSON reçu de Claude Code via stdin.

**Windows**

```powershell
# Via winget (recommandé)
winget install jqlang.jq

# Via Chocolatey
choco install jq

# Via Scoop
scoop install jq
```

**macOS**

```bash
brew install jq
```

**Linux**

```bash
sudo apt install jq        # Debian/Ubuntu
sudo dnf install jq        # Fedora/RHEL
```

Vérifier : `jq --version`

### bash (obligatoire)

**Windows** : installer [Git for Windows](https://git-scm.com/download/win) — fournit Git Bash avec bash, awk et curl inclus.

**macOS / Linux** : bash est natif.

---

## Installation

### 1. Copier le script

```bash
cp statusline.sh ~/.claude/statusline.sh
chmod +x ~/.claude/statusline.sh
```

### 2. Configurer `~/.claude/settings.json`

Ouvrir avec nano :

```bash
nano ~/.claude/settings.json
```

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

> **Windows** : utiliser des slashes forward (`C:/Users/...`) et préfixer avec `bash` — la tilde `~` n'est pas développée par Claude Code sur Windows.

Sauvegarder dans nano : `Ctrl+O` puis `Entrée`, quitter : `Ctrl+X`.

### 3. Redémarrer Claude Code

La statusline se rafraîchit automatiquement toutes les `refreshInterval` secondes (10 par défaut).

---

## Dépannage

**La statusline n'apparaît pas du tout**

- Vérifier que `bash` est dans le PATH : `where bash` (PowerShell)
- Vérifier que `jq` est dans le PATH : `jq --version` dans Git Bash

**Caractère `󰥔` affiché comme carré**

- Ce caractère nécessite une [Nerd Font](https://www.nerdfonts.com/). Le remplacer par `⏱` ou le texte `5h:` dans le script si votre terminal n'a pas de Nerd Font.

**Affiché `quota: en attente...`**

- Normal avant la première réponse de l'API dans une session. Disparaît après le premier échange.

**Debug — inspecter le JSON brut reçu**

```bash
# Ajouter temporairement après la ligne `input=$(cat)` :
echo "$input" > "$HOME/statusline-debug.json"
# Puis lire : cat C:/Users/<VotreNom>/statusline-debug.json
```
