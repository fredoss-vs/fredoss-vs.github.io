# MMM-Timer

Module [MagicMirror²](https://github.com/MagicMirrorOrg/MagicMirror) de **compte à rebours plein écran**, tactile, avec **verrouillage de page via MMM-pages** et **alerte visuelle clignotante** en fin de décompte.

Compatible MagicMirror² ≥ 2.33 (validé contre la 2.36.0). JavaScript natif, aucune dépendance externe, aucun `node_helper` (module 100 % frontend).

---

## Fonctionnalités

- Affichage **HH:MM:SS** centré horizontalement et verticalement, police large lisible à distance.
- Durée configurable directement à l'écran (boutons tactiles **+ / −** pour heures, minutes, secondes) lorsque le timer est à l'arrêt.
- Contrôles tactiles : **Démarrer**, **Pause**, **Reprendre**, **Réinitialiser** (icônes Font Awesome fournies par MagicMirror²).
- **Verrouillage de page** : au démarrage du timer, bascule automatique sur la page cible MMM-pages, rotation automatique suspendue (`PAUSE_ROTATION`) et toute tentative de changement de page (manuelle ou émise par un autre module) est immédiatement annulée via l'écoute du broadcast `NEW_PAGE`.
- **Fin de décompte** : clignotement rouge continu de tout l'écran jusqu'à l'appui sur le bouton **STOP**, qui arrête l'alerte, réinitialise le timer, supprime le verrouillage et réactive la rotation (`RESUME_ROTATION`).
- Précision du décompte basée sur un horodatage absolu (`Date.now()`), insensible à la dérive du `setInterval` (adapté au Raspberry Pi 3B).

---

## États du module

| État | Affichage | Contrôles |
|---|---|---|
| `IDLE` | Durée configurée, éditable (+/−) | Démarrer |
| `RUNNING` | Temps restant, décompte actif | Pause · Réinitialiser |
| `PAUSED` | Temps restant figé | Reprendre · Réinitialiser |
| `FINISHED` | 00:00:00, écran clignotant rouge | STOP |

---

## Installation

```bash
cd ~/MagicMirror/modules
git clone <votre-dépôt>/MMM-Timer.git
# — ou copie manuelle du dossier MMM-Timer/ dans ~/MagicMirror/modules/
```

Aucune installation npm n'est nécessaire (`npm install` inutile — pas de dépendance).

### Arborescence

```
MagicMirror/modules/MMM-Timer/
├── MMM-Timer.js     # Module frontend (logique + DOM)
├── MMM-Timer.css    # Styles (centrage, tactile, clignotement)
├── package.json     # Métadonnées
└── README.md        # Cette documentation
```

---

## Configuration

### Exemple complet (`config/config.js`)

> **Important — indexation MMM-pages :** les pages sont indexées à partir de **0**. `targetPage` doit contenir l'**index** de la page sur laquelle le timer est affiché. Pour une installation à 5 pages, la 5ᵉ page porte l'index **4**.

```js
modules: [
    // ... autres modules ...

    {
        module: "MMM-pages",
        config: {
            modules: [
                ["clock", "calendar", "weather-current", "weather-forecast", "page-news"], // page 0
                ["page-stocks"],   // page 1
                ["page-mqtt"],     // page 2
                ["page-newsapi"],  // page 3
                ["page-timer"]     // page 4  ← page du timer (5ᵉ page)
            ],
            fixed: ["MMM-page-indicator"],
            timings: { default: 30000 },
            animationTime: 1000
        }
    },

    {
        module: "MMM-Timer",
        position: "fullscreen_above",
        classes: "page-timer",          // rattache le module à la page MMM-pages
        config: {
            defaultHours: 0,
            defaultMinutes: 15,
            defaultSeconds: 0,

            // Affichage
            showControls: true,
            timerFontSize: "8rem",

            // Alerte de fin
            flashColor: "#ff0000",
            flashInterval: 500,

            // Gestion des pages MagicMirror²
            lockPageOnStart: true,
            targetPage: 4,              // index 0-based de la page du timer
            restoreNavigationOnStop: true,

            // Comportement après arrêt
            autoResetAfterStop: true
        }
    }
]
```

### Paramètres

| Paramètre | Type | Défaut | Description |
|---|---|---|---|
| `defaultHours` | `int` | `0` | Heures par défaut (0–99) |
| `defaultMinutes` | `int` | `15` | Minutes par défaut (0–59) |
| `defaultSeconds` | `int` | `0` | Secondes par défaut (0–59) |
| `showControls` | `bool` | `true` | Affiche ou masque les boutons de contrôle |
| `timerFontSize` | `string` | `"8rem"` | Taille du texte du timer (toute unité CSS) |
| `flashColor` | `string` | `"#ff0000"` | Couleur du clignotement de fin |
| `flashInterval` | `int` | `500` | Demi-période du clignotement (ms) |
| `lockPageOnStart` | `bool` | `true` | Verrouille l'affichage sur `targetPage` au démarrage du timer |
| `targetPage` | `int` | `5` | **Index 0-based** de la page MMM-pages à verrouiller |
| `restoreNavigationOnStop` | `bool` | `true` | Réactive la rotation MMM-pages après STOP / réinitialisation |
| `autoResetAfterStop` | `bool` | `true` | Réinitialise automatiquement le timer après STOP ; si `false`, le timer reste à `00:00:00` jusqu'à appui sur Réinitialiser |

---

## Utilisation

1. **Naviguer** vers la page du timer (rotation automatique, MMM-page-indicator ou geste tactile selon votre installation).
2. **Régler la durée** avec les boutons **+ / −** au-dessus et en dessous de chaque groupe de chiffres (heures, minutes, secondes). Les valeurs sont cycliques (59 + 1 → 0).
3. **Démarrer** (▶) : le décompte commence, le miroir bascule et reste verrouillé sur la page du timer ; la rotation automatique et la navigation manuelle sont neutralisées.
4. **Pause** (⏸) / **Reprendre** (▶) : suspend et reprend le décompte, le temps restant est conservé.
5. **Réinitialiser** (↺) : arrête le décompte, restaure la navigation et revient à la durée configurée (à nouveau modifiable).
6. À **00:00:00**, l'écran entier clignote en rouge en continu. Appuyer sur **STOP** (⏹) pour : arrêter le clignotement, réinitialiser le timer, supprimer le verrouillage et rétablir le fonctionnement normal des pages.

---

## Intégration MMM-pages — détails techniques

| Notification | Sens | Rôle |
|---|---|---|
| `PAGE_SELECT` | MMM-Timer → MMM-pages | Bascule sur `targetPage` (payload = index 0-based) |
| `PAUSE_ROTATION` | MMM-Timer → MMM-pages | Suspend la rotation automatique |
| `RESUME_ROTATION` | MMM-Timer → MMM-pages | Réactive la rotation |
| `NEW_PAGE` | MMM-pages → broadcast | Écoutée par MMM-Timer : si la page diffère de `targetPage` pendant le verrouillage, retour forcé immédiat |

> `PAGE_SELECT` remplace `PAGE_CHANGED`, dépréciée dans les versions récentes de MMM-pages.

Le module doit porter la classe (`classes: "page-timer"`) référencée dans la configuration MMM-pages, faute de quoi MMM-pages le masquera en permanence.

---

## Notes

- Position recommandée : `fullscreen_above` (le module réactive `pointer-events` pour le tactile, MagicMirror² les désactivant par défaut sur les régions plein écran).
- Testé sur Raspberry Pi 3B + écran tactile DSI OSOYOO 5" (800 × 480) sous Chromium/Wayfire en mode kiosk.
- Aucun secret ni accès réseau : le module fonctionne intégralement côté navigateur.

## Licence

MIT
