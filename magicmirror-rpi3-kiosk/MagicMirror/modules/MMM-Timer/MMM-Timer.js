/**
 * MMM-Timer
 *
 * Module MagicMirror² — Compte à rebours plein écran avec verrouillage
 * de page via MMM-pages et alerte visuelle clignotante en fin de décompte.
 *
 * États du module :
 *   IDLE     → durée configurable (boutons +/-), bouton Démarrer
 *   RUNNING  → décompte actif, page verrouillée, boutons Pause / Réinitialiser
 *   PAUSED   → décompte suspendu, boutons Reprendre / Réinitialiser
 *   FINISHED → 00:00:00 atteint, clignotement rouge continu, bouton STOP
 *
 * Intégration MMM-pages (testée avec la version installée localement) :
 *   - Envoi  : PAGE_SELECT (payload = index 0-based), PAUSE_ROTATION, RESUME_ROTATION
 *   - Écoute : NEW_PAGE (broadcast par MMM-pages à chaque changement de page)
 *   - Le verrouillage est défensif : toute tentative de changement de page
 *     pendant l'exécution du timer est immédiatement annulée.
 *
 * Aucune dépendance externe. JavaScript natif uniquement.
 * Compatible MagicMirror² ≥ 2.33 (validé contre la 2.36.0).
 *
 * Licence : MIT
 */

/* global Module, Log */

Module.register("MMM-Timer", {

	// ---------------------------------------------------------------------
	// Configuration par défaut
	// ---------------------------------------------------------------------
	defaults: {
		// Durée initiale du compte à rebours
		defaultHours: 0,
		defaultMinutes: 15,
		defaultSeconds: 0,

		// Affichage
		showControls: true, // affiche les boutons de contrôle
		timerFontSize: "8rem", // taille de la police du timer

		// Alerte de fin
		flashColor: "#ff0000", // couleur du clignotement
		flashInterval: 500, // demi-période du clignotement (ms)

		// Gestion des pages MMM-pages
		lockPageOnStart: true, // verrouille l'affichage au démarrage du timer
		targetPage: 5, // index MMM-pages (0-based !) de la page à verrouiller
		restoreNavigationOnStop: true, // réactive la rotation après STOP / reset

		// Comportement après appui sur STOP
		autoResetAfterStop: true // remet automatiquement le timer à la durée configurée
	},

	// ---------------------------------------------------------------------
	// Cycle de vie
	// ---------------------------------------------------------------------

	/**
	 * Initialisation du module : état interne et durée de départ.
	 */
	start () {
		// État courant : IDLE | RUNNING | PAUSED | FINISHED
		this.state = "IDLE";

		// Durée configurée (modifiable via l'éditeur tactile quand IDLE)
		this.duration = {
			hours: this.clampInt(this.config.defaultHours, 0, 99),
			minutes: this.clampInt(this.config.defaultMinutes, 0, 59),
			seconds: this.clampInt(this.config.defaultSeconds, 0, 59)
		};

		// Temps restant en millisecondes
		this.remainingMs = this.durationToMs();

		// Horodatage absolu de fin (précision indépendante du setInterval)
		this.endTime = null;

		// Handle du setInterval de décompte
		this.tickInterval = null;

		// Indicateurs
		this.pageLocked = false; // verrouillage de page actif
		this.alarmActive = false; // clignotement en cours

		// Références DOM mises à jour sans re-render complet
		this.timeEl = null;
		this.editorValueEls = {};

		Log.info(`[${this.name}] démarré — durée par défaut ${this.formatTime(this.remainingMs)}`);
	},

	/**
	 * Feuilles de style : Font Awesome (fourni par MagicMirror²) + CSS du module.
	 * @returns {Array<string>} liste des fichiers CSS à charger
	 */
	getStyles () {
		return ["font-awesome.css", "MMM-Timer.css"];
	},

	// ---------------------------------------------------------------------
	// Rendu DOM
	// ---------------------------------------------------------------------

	/**
	 * Construit l'intégralité de l'interface selon l'état courant.
	 * @returns {HTMLElement} le wrapper du module
	 */
	getDom () {
		const wrapper = document.createElement("div");
		wrapper.className = `mmm-timer mmm-timer--${this.state.toLowerCase()}`;
		if (this.alarmActive) {
			wrapper.classList.add("mmm-timer--alarm");
		}

		// Variables CSS pilotées par la configuration
		wrapper.style.setProperty("--mmm-timer-font-size", this.config.timerFontSize);
		wrapper.style.setProperty("--mmm-timer-flash-color", this.config.flashColor);
		wrapper.style.setProperty("--mmm-timer-flash-duration", `${this.config.flashInterval * 2}ms`);

		const content = document.createElement("div");
		content.className = "mmm-timer__content";

		// Affichage principal : éditeur (IDLE) ou décompte (autres états)
		if (this.state === "IDLE") {
			content.appendChild(this.buildEditor());
		} else {
			content.appendChild(this.buildDisplay());
		}

		// Boutons de contrôle
		if (this.config.showControls) {
			content.appendChild(this.buildControls());
		}

		wrapper.appendChild(content);
		return wrapper;
	},

	/**
	 * Éditeur de durée (état IDLE) : pour chaque unité (HH/MM/SS),
	 * un bouton « + » au-dessus et un bouton « − » en dessous.
	 * Compatible tactile, valeurs cycliques (wrap-around).
	 * @returns {HTMLElement} l'éditeur
	 */
	buildEditor () {
		const editor = document.createElement("div");
		editor.className = "mmm-timer__editor";
		this.editorValueEls = {};

		const units = [
			{ key: "hours", max: 99 },
			{ key: "minutes", max: 59 },
			{ key: "seconds", max: 59 }
		];

		units.forEach((unit, index) => {
			// Séparateur « : » entre les groupes de chiffres
			if (index > 0) {
				const colon = document.createElement("div");
				colon.className = "mmm-timer__colon";
				colon.textContent = ":";
				editor.appendChild(colon);
			}

			const column = document.createElement("div");
			column.className = "mmm-timer__unit";

			// Bouton « + »
			column.appendChild(this.makeAdjustButton("fa-chevron-up", () => {
				this.adjustDuration(unit.key, 1, unit.max);
			}));

			// Valeur affichée (2 chiffres)
			const value = document.createElement("div");
			value.className = "mmm-timer__digits";
			value.textContent = this.pad(this.duration[unit.key]);
			this.editorValueEls[unit.key] = value;
			column.appendChild(value);

			// Bouton « − »
			column.appendChild(this.makeAdjustButton("fa-chevron-down", () => {
				this.adjustDuration(unit.key, -1, unit.max);
			}));

			editor.appendChild(column);
		});

		return editor;
	},

	/**
	 * Affichage du décompte (états RUNNING / PAUSED / FINISHED) au format HH:MM:SS.
	 * @returns {HTMLElement} l'affichage du temps restant
	 */
	buildDisplay () {
		const display = document.createElement("div");
		display.className = "mmm-timer__display mmm-timer__digits";
		display.textContent = this.formatTime(this.remainingMs);
		this.timeEl = display;
		return display;
	},

	/**
	 * Barre de boutons contextuelle selon l'état courant.
	 * @returns {HTMLElement} la barre de contrôles
	 */
	buildControls () {
		const controls = document.createElement("div");
		controls.className = "mmm-timer__controls";

		switch (this.state) {
			case "IDLE":
				controls.appendChild(this.makeButton("fa-play", "Démarrer", () => this.startTimer()));
				break;

			case "RUNNING":
				controls.appendChild(this.makeButton("fa-pause", "Pause", () => this.pauseTimer()));
				controls.appendChild(this.makeButton("fa-rotate-left", "Réinitialiser", () => this.resetTimer()));
				break;

			case "PAUSED":
				controls.appendChild(this.makeButton("fa-play", "Reprendre", () => this.resumeTimer()));
				controls.appendChild(this.makeButton("fa-rotate-left", "Réinitialiser", () => this.resetTimer()));
				break;

			case "FINISHED":
				if (this.alarmActive) {
					controls.appendChild(this.makeButton("fa-stop", "STOP", () => this.stopAlarm(), "mmm-timer__button--stop"));
				} else {
					controls.appendChild(this.makeButton("fa-rotate-left", "Réinitialiser", () => this.resetTimer()));
				}
				break;

			default:
				break;
		}

		return controls;
	},

	/**
	 * Fabrique un bouton de contrôle tactile (icône Font Awesome + libellé).
	 * @param {string} icon classe Font Awesome (ex. "fa-play")
	 * @param {string} label libellé affiché sous l'icône
	 * @param {Function} onClick callback au clic / appui tactile
	 * @param {string} [extraClass] classe CSS additionnelle
	 * @returns {HTMLElement} le bouton
	 */
	makeButton (icon, label, onClick, extraClass) {
		const button = document.createElement("button");
		button.type = "button";
		button.className = `mmm-timer__button${extraClass ? ` ${extraClass}` : ""}`;
		button.setAttribute("aria-label", label);

		const iconEl = document.createElement("i");
		iconEl.className = `fa fa-fw ${icon}`;
		button.appendChild(iconEl);

		const labelEl = document.createElement("span");
		labelEl.className = "mmm-timer__button-label";
		labelEl.textContent = label;
		button.appendChild(labelEl);

		button.addEventListener("click", (event) => {
			event.preventDefault();
			onClick();
		});

		return button;
	},

	/**
	 * Fabrique un bouton « + » / « − » de l'éditeur de durée.
	 * @param {string} icon classe Font Awesome (chevron haut/bas)
	 * @param {Function} onClick callback au clic / appui tactile
	 * @returns {HTMLElement} le bouton d'ajustement
	 */
	makeAdjustButton (icon, onClick) {
		const button = document.createElement("button");
		button.type = "button";
		button.className = "mmm-timer__adjust";

		const iconEl = document.createElement("i");
		iconEl.className = `fa fa-fw ${icon}`;
		button.appendChild(iconEl);

		button.addEventListener("click", (event) => {
			event.preventDefault();
			onClick();
		});

		return button;
	},

	// ---------------------------------------------------------------------
	// Logique du timer
	// ---------------------------------------------------------------------

	/**
	 * Ajuste une unité de la durée configurée (uniquement à l'état IDLE).
	 * Les valeurs sont cycliques : 59 + 1 → 0, 0 − 1 → 59.
	 * Mise à jour directe du DOM (pas de re-render complet) pour rester
	 * réactif au tapotement rapide sur écran tactile.
	 * @param {string} unit "hours" | "minutes" | "seconds"
	 * @param {number} delta +1 ou -1
	 * @param {number} max valeur maximale de l'unité
	 */
	adjustDuration (unit, delta, max) {
		if (this.state !== "IDLE") {
			return;
		}
		const range = max + 1;
		this.duration[unit] = (this.duration[unit] + delta + range) % range;
		this.remainingMs = this.durationToMs();

		const el = this.editorValueEls[unit];
		if (el) {
			el.textContent = this.pad(this.duration[unit]);
		}
	},

	/**
	 * Démarre le compte à rebours à partir de la durée configurée
	 * et verrouille la page MMM-pages si demandé.
	 */
	startTimer () {
		if (this.state !== "IDLE") {
			return;
		}
		this.remainingMs = this.durationToMs();
		if (this.remainingMs <= 0) {
			Log.warn(`[${this.name}] durée nulle — démarrage ignoré`);
			return;
		}

		this.state = "RUNNING";
		this.endTime = Date.now() + this.remainingMs;
		this.startTick();
		this.lockPage();
		this.updateDom();
		Log.info(`[${this.name}] démarrage — ${this.formatTime(this.remainingMs)}`);
	},

	/**
	 * Met le décompte en pause ; le temps restant est conservé.
	 */
	pauseTimer () {
		if (this.state !== "RUNNING") {
			return;
		}
		this.stopTick();
		this.remainingMs = Math.max(0, this.endTime - Date.now());
		this.state = "PAUSED";
		this.updateDom();
		Log.info(`[${this.name}] pause — reste ${this.formatTime(this.remainingMs)}`);
	},

	/**
	 * Reprend le décompte depuis la valeur restante.
	 */
	resumeTimer () {
		if (this.state !== "PAUSED") {
			return;
		}
		this.state = "RUNNING";
		this.endTime = Date.now() + this.remainingMs;
		this.startTick();
		this.updateDom();
		Log.info(`[${this.name}] reprise — reste ${this.formatTime(this.remainingMs)}`);
	},

	/**
	 * Arrête le décompte, restaure la navigation et remet le timer
	 * à la durée initialement configurée (état IDLE, durée modifiable).
	 */
	resetTimer () {
		this.stopTick();
		this.state = "IDLE";
		this.alarmActive = false;
		this.endTime = null;
		this.remainingMs = this.durationToMs();
		this.unlockPage();
		this.updateDom();
		Log.info(`[${this.name}] réinitialisation`);
	},

	/**
	 * Fin du décompte : passe en état FINISHED et déclenche
	 * le clignotement continu. La page reste verrouillée jusqu'au STOP.
	 */
	finishTimer () {
		this.stopTick();
		this.remainingMs = 0;
		this.state = "FINISHED";
		this.alarmActive = true;
		this.updateDom();
		Log.info(`[${this.name}] terminé — alerte visuelle active`);
	},

	/**
	 * Action du bouton STOP pendant l'alerte :
	 *   - arrêt immédiat du clignotement,
	 *   - suppression du verrouillage de page,
	 *   - réactivation de la rotation MMM-pages (selon configuration),
	 *   - réinitialisation automatique (selon configuration).
	 */
	stopAlarm () {
		if (this.state !== "FINISHED") {
			return;
		}
		this.alarmActive = false;
		this.unlockPage();

		if (this.config.autoResetAfterStop) {
			this.resetTimer();
		} else {
			// Le timer reste affiché à 00:00:00 ; un appui sur
			// « Réinitialiser » est nécessaire pour reconfigurer.
			this.updateDom();
		}
		Log.info(`[${this.name}] STOP — alerte arrêtée, navigation restaurée`);
	},

	// ---------------------------------------------------------------------
	// Décompte interne
	// ---------------------------------------------------------------------

	/**
	 * Lance la boucle de décompte. Le temps restant est recalculé à partir
	 * de l'horodatage absolu de fin (this.endTime), ce qui garantit la
	 * précision même si le setInterval dérive (charge CPU du Pi, etc.).
	 */
	startTick () {
		this.stopTick();
		this.tickInterval = setInterval(() => this.tick(), 250);
	},

	/**
	 * Arrête la boucle de décompte.
	 */
	stopTick () {
		if (this.tickInterval) {
			clearInterval(this.tickInterval);
			this.tickInterval = null;
		}
	},

	/**
	 * Itération de décompte : met à jour l'affichage sans re-render complet.
	 */
	tick () {
		const remaining = this.endTime - Date.now();
		if (remaining <= 0) {
			this.finishTimer();
			return;
		}
		this.remainingMs = remaining;
		if (this.timeEl) {
			this.timeEl.textContent = this.formatTime(remaining);
		}
	},

	// ---------------------------------------------------------------------
	// Intégration MMM-pages
	// ---------------------------------------------------------------------

	/**
	 * Verrouille l'affichage sur la page cible :
	 *   - PAUSE_ROTATION : stoppe la rotation automatique de MMM-pages,
	 *   - PAGE_SELECT : bascule sur la page cible (index 0-based).
	 */
	lockPage () {
		if (!this.config.lockPageOnStart) {
			return;
		}
		this.pageLocked = true;
		this.sendNotification("PAUSE_ROTATION");
		this.sendNotification("PAGE_SELECT", this.config.targetPage);
		Log.info(`[${this.name}] page ${this.config.targetPage} verrouillée`);
	},

	/**
	 * Supprime le verrouillage et réactive la rotation MMM-pages
	 * (rotation automatique et navigation manuelle).
	 */
	unlockPage () {
		if (!this.pageLocked) {
			return;
		}
		this.pageLocked = false;
		if (this.config.restoreNavigationOnStop) {
			this.sendNotification("RESUME_ROTATION");
		}
		Log.info(`[${this.name}] verrouillage de page supprimé`);
	},

	/**
	 * Verrouillage défensif : MMM-pages broadcast NEW_PAGE à chaque
	 * changement de page. Si une page différente de la cible apparaît
	 * pendant le verrouillage (rotation résiduelle, navigation manuelle,
	 * notification d'un autre module), on force le retour immédiat.
	 * @param {string} notification identifiant de la notification
	 * @param {*} payload contenu de la notification
	 */
	notificationReceived (notification, payload) {
		if (!this.pageLocked) {
			return;
		}
		if (notification === "NEW_PAGE" && Number(payload) !== Number(this.config.targetPage)) {
			Log.warn(`[${this.name}] changement de page bloqué (page ${payload}) — retour forcé sur ${this.config.targetPage}`);
			this.sendNotification("PAUSE_ROTATION");
			this.sendNotification("PAGE_SELECT", this.config.targetPage);
		}
	},

	/**
	 * Au retour sur la page du module, resynchronise l'affichage.
	 */
	resume () {
		this.updateDom();
	},

	// ---------------------------------------------------------------------
	// Utilitaires
	// ---------------------------------------------------------------------

	/**
	 * Convertit la durée configurée en millisecondes.
	 * @returns {number} durée en ms
	 */
	durationToMs () {
		return ((this.duration.hours * 3600) + (this.duration.minutes * 60) + this.duration.seconds) * 1000;
	},

	/**
	 * Formate une durée en millisecondes au format HH:MM:SS.
	 * Arrondi à la seconde supérieure pour que l'affichage démarre
	 * sur la durée pleine et termine exactement à 00:00:00.
	 * @param {number} ms durée en millisecondes
	 * @returns {string} chaîne "HH:MM:SS"
	 */
	formatTime (ms) {
		const totalSeconds = Math.max(0, Math.ceil(ms / 1000));
		const hours = Math.floor(totalSeconds / 3600);
		const minutes = Math.floor((totalSeconds % 3600) / 60);
		const seconds = totalSeconds % 60;
		return `${this.pad(hours)}:${this.pad(minutes)}:${this.pad(seconds)}`;
	},

	/**
	 * Formate un entier sur 2 chiffres.
	 * @param {number} value valeur à formater
	 * @returns {string} valeur sur 2 chiffres
	 */
	pad (value) {
		return String(value).padStart(2, "0");
	},

	/**
	 * Convertit et borne une valeur entière dans [min, max].
	 * @param {*} value valeur d'entrée (config utilisateur)
	 * @param {number} min borne inférieure
	 * @param {number} max borne supérieure
	 * @returns {number} entier borné
	 */
	clampInt (value, min, max) {
		const parsed = parseInt(value, 10);
		if (Number.isNaN(parsed)) {
			return min;
		}
		return Math.min(max, Math.max(min, parsed));
	}
});
