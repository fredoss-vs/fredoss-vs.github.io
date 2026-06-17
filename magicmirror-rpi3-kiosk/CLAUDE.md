# Agent — Développement MagicMirror²

Spécialiste du développement sur [MagicMirror²](https://github.com/MagicMirrorOrg/MagicMirror), plateforme open-source de miroir connecté modulaire basée sur Electron + Node.js.

---

## Stack technique

| Couche | Technologie |
|--------|-------------|
| Affichage | Electron 41.x (Chromium embarqué) |
| Serveur | Node.js ≥22.21.1 (hors 23) ou ≥24 + Express 5.x |
| Temps réel | Socket.io 4.x (namespaces par module) |
| Templating | Nunjucks 3.x |
| Tests | Vitest (unit) + tests e2e |
| Linting | ESLint (`eslint.config.mjs`) + Prettier (`prettier.config.mjs`) + Stylelint (`stylelint.config.mjs`) |
| Langages | JavaScript 84 %, HTML 9 %, CSS 6 %, Nunjucks 2 % |

---

## Structure du projet

```
MagicMirror/
├── config/           # config.js (utilisateur) — copié depuis config.js.sample
├── css/              # Styles globaux
├── js/               # Core : module.js, node_helper.js, loader, logger…
├── modules/
│   └── default/      # Modules intégrés (clock, weather, calendar…)
├── serveronly/       # Code exécuté côté Node uniquement
├── clientonly/       # Code exécuté côté Electron/navigateur uniquement
└── translations/     # Fichiers i18n globaux
```

---

## Commandes essentielles

```bash
# Démarrer l'application
npm run start           # Wayland (Raspberry Pi récent)
npm run start:x11       # X11 (Raspberry Pi / Linux classique)
npm run start:windows   # Windows

# Mode serveur headless (sans Electron)
npm run server
npm run server:watch    # Avec rechargement à chaud

# Tests
npm test                # Suite complète
npm run test:unit       # Tests unitaires (Vitest)
npm run test:e2e        # Tests end-to-end
npm run test:coverage   # Couverture de code
npm run test:ui         # Interface Vitest UI

# Qualité de code
npm run lint:js
npm run lint:css
npm run lint:markdown
npm run lint:prettier

# Vérification config
npm run config:check
npm run test:spelling
```

---

## Anatomie d'un module

Un module vit dans `modules/MMM-MonModule/` et contient :

```
MMM-MonModule/
├── MMM-MonModule.js       # Fichier principal (frontend / Electron)
├── node_helper.js         # Backend Node.js (optionnel)
├── MMM-MonModule.css      # Styles (optionnel)
├── package.json           # Métadonnées + dépendances npm
└── translations/
    └── fr.json            # Traductions (optionnel)
```

**Convention de nommage :** préfixe `MMM-` obligatoire pour les modules tiers.

---

## API du module frontend (`MMM-MonModule.js`)

```js
Module.register("MMM-MonModule", {

  // --- Propriétés de configuration ---
  defaults: {
    updateInterval: 60000,
    option: "valeur"
  },

  // --- Méthodes à surcharger ---

  init() {},           // Instanciation (avant start)
  start() {},          // Démarrage — bon endroit pour setInterval / sendSocketNotification

  getScripts()      { return ["moment.js"]; },         // JS à charger (chemins relatifs ou URL)
  getStyles()       { return ["MMM-MonModule.css"]; }, // CSS à charger
  getTranslations() { return { fr: "translations/fr.json" }; },

  getDom() {
    // Retourne un HTMLElement ou une Promise<HTMLElement>
    const wrapper = document.createElement("div");
    wrapper.className = "MMM-MonModule";
    wrapper.innerHTML = this.translate("HELLO");
    return wrapper;
  },

  getHeader() { return this.config.header ?? "Mon Module"; },

  // Templating Nunjucks (alternative à getDom)
  getTemplate()     { return "template.njk"; },
  getTemplateData() { return { data: this.data }; },

  notificationReceived(notification, payload, sender) {
    // Notifications inter-modules et système
    // Ex: "DOM_OBJECTS_CREATED", "MODULE_DOM_CREATED", "CLOCK_SECOND"
  },

  socketNotificationReceived(notification, payload) {
    // Réponses depuis node_helper.js
    if (notification === "DATA_FETCHED") {
      this.data = payload;
      this.updateDom();
    }
  },

  suspend() {}, // Module masqué
  resume()  {}, // Module réaffiché

  // --- Méthodes core (ne pas surcharger) ---

  // updateDom(animationSpeed?)  — Demande un re-render
  // sendNotification(notif, payload)         — Broadcast à tous les modules
  // sendSocketNotification(notif, payload)   — Envoi vers node_helper
  // hide(speed, callback?, options?)
  // show(speed, callback?, options?)
  // translate(key, variables?, default?)
  // file(filename)   — Chemin absolu vers un fichier du module
  // nunjucksEnvironment()
});
```

---

## API du node_helper (`node_helper.js`)

```js
const NodeHelper = require("node_helper");

module.exports = NodeHelper.create({

  start() {
    // Initialisation côté serveur
    console.log("MMM-MonModule helper started");
  },

  stop() {
    // Nettoyage à l'arrêt (SIGINT)
  },

  socketNotificationReceived(notification, payload) {
    if (notification === "FETCH_DATA") {
      this.fetchData(payload.url);
    }
  },

  async fetchData(url) {
    try {
      const response = await fetch(url);
      NodeHelper.checkFetchStatus(response); // Lance une erreur si !response.ok
      const data = await response.json();
      this.sendSocketNotification("DATA_FETCHED", data);
    } catch (err) {
      this.sendSocketNotification("FETCH_ERROR", err.message);
    }
  }
});

// Utilitaires statiques disponibles :
// NodeHelper.checkFetchStatus(response)  — Valide HTTP status
// NodeHelper.checkFetchError(error)      — Mappe erreur → code traduit
```

**Communication :** Socket.io avec namespace par module. `sendSocketNotification` → `socketNotificationReceived` dans les deux sens.

---

## Configuration (`config/config.js`)

```js
let config = {
  address: "localhost",
  port: 8080,
  basePath: "/",
  ipWhitelist: ["127.0.0.1", "::1"],
  useHttps: false,
  language: "fr",
  locale: "fr-FR",
  logLevel: ["INFO", "LOG", "WARN", "ERROR"],
  timeFormat: 24,
  units: "metric",
  serverOnly: false,
  hideConfigSecrets: true,  // Masque les secrets dans les logs socket

  modules: [
    {
      module: "MMM-MonModule",
      position: "top_right",          // Voir positions disponibles ci-dessous
      header: "Titre affiché",
      disabled: false,
      config: {
        option: "valeur"
      }
    }
  ]
};
```

**Positions disponibles :**
`top_bar` · `top_left` · `top_center` · `top_right` · `upper_third` · `middle_center` · `lower_third` · `bottom_left` · `bottom_center` · `bottom_right` · `bottom_bar` · `fullscreen_above` · `fullscreen_below`

---

## Notifications système importantes

| Notification | Sens | Déclenchement |
|---|---|---|
| `DOM_OBJECTS_CREATED` | Core → modules | DOM initialisé |
| `MODULE_DOM_CREATED` | Core → modules | DOM du module prêt |
| `ALL_MODULES_STARTED` | Core → modules | Tous les modules démarrés |
| `CLOCK_SECOND` | clock → modules | Chaque seconde |
| `CLOCK_MINUTE` | clock → modules | Chaque minute |
| `CALENDAR_EVENTS` | calendar → modules | Mise à jour agenda |
| `SHOW_ALERT` | modules → alert | Afficher une alerte |
| `HIDE_ALERT` | modules → alert | Masquer une alerte |

---

## Règles de développement

- **Linting avant commit** : ESLint + Prettier sont obligatoires ; `npm run lint:js` doit passer.
- **Tests unitaires** : Vitest dans `tests/unit/`. Toute nouvelle fonctionnalité core doit être testée.
- **Pas de `var`** : utiliser `const`/`let` exclusivement.
- **Async/await** privilégié sur les callbacks et `.then()`.
- **`fetch` natif** côté node_helper — pas d'axios ni de node-fetch pour les nouveaux modules.
- **`Logger`** au lieu de `console.log` dans le core (`Logger.info()`, `Logger.warn()`, `Logger.error()`).
- **Pas de secrets en clair** dans `config.js` versionné — utiliser `.env` ou `config.js` hors dépôt.
- **EditorConfig** : respecter `.editorconfig` (indentation, fin de ligne).

---

## Liens de référence

| Ressource | URL |
|---|---|
| Documentation officielle | https://docs.magicmirror.builders |
| Forum développeurs | https://forum.magicmirror.builders |
| Liste des modules tiers | https://github.com/MagicMirrorOrg/MagicMirror/wiki/3rd-party-modules |
| Discord | https://discord.gg/J5BAtvx |
| Dépôt GitHub | https://github.com/MagicMirrorOrg/MagicMirror |
