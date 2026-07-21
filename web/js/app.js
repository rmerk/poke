/** Pocket Pokedex — pure render + intent dispatch over PokeMachine.
 * No pipeline knowledge: never sees MIN_CONF, never threads a slug, never
 * branches on accept/ambiguous. It renders a state and forwards gestures. */

(function () {
  /**
   * @param {string} id
   * @returns {HTMLElement}
   */
  function mustEl(id) {
    var el = document.getElementById(id);
    if (!el) throw new Error("Missing #" + id);
    return el;
  }

  /**
   * @param {string} id
   * @returns {HTMLImageElement}
   */
  function mustImg(id) {
    return /** @type {HTMLImageElement} */ (mustEl(id));
  }

  /**
   * @param {string} id
   * @returns {HTMLInputElement}
   */
  function mustInput(id) {
    return /** @type {HTMLInputElement} */ (mustEl(id));
  }

  /** @type {{ [key: string]: HTMLElement }} */
  var screens = {
    idle: mustEl("screen-idle"),
    busy: mustEl("screen-busy"),
    preview: mustEl("screen-preview"),
    search: mustEl("screen-search"),
    entry: mustEl("screen-entry"),
    error: mustEl("screen-error"),
  };

  // ------------------------------------------------------------- copy

  /**
   * @param {BusyPhase} phase
   * @returns {string}
   */
  function busyTitle(phase) {
    switch (phase.kind) {
      case "demo":
        return "Demo…";
      case "ocr":
        return "Reading card…";
      case "lookup":
        return "Looking up " + phase.name + "…";
      default:
        return assertNever(phase);
    }
  }

  /**
   * @param {UnresolvedReason | null} reason
   * @returns {string}
   */
  function searchStatus(reason) {
    if (!reason) return "Type a Pokémon name (offline list).";
    switch (reason.kind) {
      case "low-confidence":
        return "Low confidence (" + Math.round(reason.score) + "). Confirm or type a name.";
      case "ambiguous":
        return "Too close to call between " + reason.count + " matches. Confirm or type a name.";
      case "ocr-timeout":
        return "OCR timed out. Search instead — still offline.";
      case "ocr-failed":
        return "OCR failed (" + reason.message + "). Search instead — still offline.";
      case "empty-query":
        return "Type a Pokémon name (offline list).";
      default:
        return assertNever(reason);
    }
  }

  /**
   * @param {never} x
   * @returns {never}
   */
  function assertNever(x) {
    throw new Error("Unhandled variant: " + JSON.stringify(x));
  }

  // ------------------------------------------------------------- type theming

  /** Canonical type → accent color. Keyed by lowercased type name. */
  /** @type {{ [type: string]: string }} */
  var TYPE_COLORS = {
    normal: "#9099a1",
    fire: "#f0803c",
    water: "#4d90d5",
    electric: "#f4c430",
    grass: "#63bb5b",
    ice: "#74cec0",
    fighting: "#ce4069",
    poison: "#ab6ac8",
    ground: "#d97845",
    flying: "#8fa8dd",
    psychic: "#f66f71",
    bug: "#90c12c",
    rock: "#c7b78b",
    ghost: "#5269ac",
    dragon: "#0a6dc4",
    dark: "#5a5366",
    steel: "#5a8ea1",
    fairy: "#ec8fe6",
  };

  /**
   * Pick readable ink (dark vs light) for a solid swatch, via luminance.
   * @param {string} hex  "#rrggbb"
   * @returns {string}
   */
  function inkOn(hex) {
    var r = parseInt(hex.slice(1, 3), 16);
    var g = parseInt(hex.slice(3, 5), 16);
    var b = parseInt(hex.slice(5, 7), 16);
    var lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
    return lum > 0.62 ? "#1b1f27" : "#ffffff";
  }

  /**
   * @param {string} type
   * @returns {string}
   */
  function typeColor(type) {
    return TYPE_COLORS[String(type || "").toLowerCase()] || "#9099a1";
  }

  // ------------------------------------------------------------- render

  /**
   * @param {MatchCandidate[]} candidates
   * @returns {void}
   */
  function renderCandidates(candidates) {
    var box = mustEl("candidates");
    box.innerHTML = "";
    for (var i = 0; i < candidates.length; i++) {
      (function (c, idx) {
        var btn = document.createElement("button");
        btn.type = "button";
        var rank = document.createElement("span");
        rank.className = "rank";
        rank.textContent = String(idx + 1);
        var name = document.createElement("span");
        name.className = "cname";
        name.textContent = c.name;
        var score = document.createElement("span");
        score.className = "cscore";
        score.textContent = "match " + Math.round(c.score);
        btn.appendChild(rank);
        btn.appendChild(name);
        btn.appendChild(score);
        btn.onclick = function () {
          PokeMachine.dispatch({ type: "CANDIDATE_PICKED", index: idx });
        };
        box.appendChild(btn);
      })(candidates[i], i);
    }
  }

  /**
   * @param {string} label
   * @param {string} value
   * @returns {HTMLElement}
   */
  function statChip(label, value) {
    var cell = document.createElement("div");
    cell.className = "stat";
    var k = document.createElement("div");
    k.className = "k";
    k.textContent = label;
    var v = document.createElement("div");
    v.className = "v";
    v.textContent = value;
    cell.appendChild(k);
    cell.appendChild(v);
    return cell;
  }

  /**
   * @param {number | null} n
   * @returns {string}
   */
  function dexLabel(n) {
    if (!n) return "No. —";
    var s = String(n);
    while (s.length < 3) s = "0" + s;
    return "No. " + s;
  }

  /**
   * Swap in the bundled species render, falling back to the Poké Ball emblem if
   * the image is missing (partial sprite set) or fails to decode. Keyed by slug
   * so it survives display-name quirks (Nidoran♀, Farfetch'd, …).
   * @param {string} slug
   * @returns {void}
   */
  function loadSprite(slug) {
    var portrait = mustEl("entry-portrait");
    var img = mustImg("entry-sprite");
    portrait.className = "portrait"; // reset to emblem until this one decodes
    img.alt = "";
    if (!slug) return;
    var want = "data/sprites/" + slug + ".png";
    img.onload = function () {
      // A stale onload from a previous species can arrive late; only reveal if
      // this is still the image we asked for.
      if (img.getAttribute("src") === want) portrait.className = "portrait has-sprite";
    };
    img.onerror = function () {
      if (img.getAttribute("src") === want) portrait.className = "portrait";
    };
    img.setAttribute("src", want);
  }

  /**
   * @param {DexEntryView} entry
   * @param {string} slug
   * @returns {void}
   */
  function renderEntry(entry, slug) {
    var section = mustEl("screen-entry");
    var types = entry.typesLine.split(" / ");
    var primary = typeColor(types[0]);
    section.style.setProperty("--accent", primary);

    loadSprite(slug);
    mustImg("entry-sprite").alt = entry.title;

    mustEl("entry-title").textContent = entry.title;
    mustEl("entry-dexno").textContent = dexLabel(entry.dexNumber);

    // Type badges — the visual identity of the scanned species.
    var badges = mustEl("entry-badges");
    badges.innerHTML = "";
    for (var t = 0; t < types.length; t++) {
      var color = typeColor(types[t]);
      var b = document.createElement("span");
      b.className = "badge";
      b.style.background = color;
      b.style.color = inkOn(color);
      b.textContent = types[t];
      badges.appendChild(b);
    }

    mustEl("entry-meta").textContent = "The " + entry.category;

    // Height · Weight → two stat chips.
    var stats = mustEl("entry-stats");
    stats.innerHTML = "";
    var hw = entry.heightWeight.split(" · ");
    stats.appendChild(statChip("Height", hw[0] || "—"));
    stats.appendChild(statChip("Weight", hw[1] || "—"));

    mustEl("entry-narration").textContent = entry.narration;

    // Facts already surfaced above (type/category/height) are dropped so the
    // list reads as extra data, not a repeat of the header.
    var ul = mustEl("entry-facts");
    ul.innerHTML = "";
    for (var i = 0; i < entry.facts.length; i++) {
      var f = entry.facts[i];
      if (/^(Type|Category|Height)\b/.test(f)) continue;
      var li = document.createElement("li");
      li.textContent = f;
      ul.appendChild(li);
    }
    mustEl("entry-attr").textContent = entry.attribution;
  }

  /**
   * Pure function of state → DOM. Never dispatches, never reads the DOM back.
   * @param {PokeState} state
   * @param {PokeState | null} prev
   * @returns {void}
   */
  function render(state, prev) {
    var key;
    for (key in screens) {
      if (Object.prototype.hasOwnProperty.call(screens, key)) {
        screens[key].className = "screen" + (key === state.screen ? " active" : "");
      }
    }

    switch (state.screen) {
      case "idle":
        return;
      case "busy":
        mustEl("busy-title").textContent = busyTitle(state.phase);
        mustEl("busy-status").textContent = state.detail;
        return;
      case "preview":
        if (!prev || prev.screen !== "preview" || prev.image !== state.image) {
          mustImg("preview-img").src = state.image.src;
        }
        mustEl("preview-status").textContent =
          "Fill the red box with the card's name — move closer if it looks small, then Identify.";
        return;
      case "search":
        mustEl("search-status").textContent = searchStatus(state.reason);
        // Rebuilding buttons is the one costly op here — skip it unless the
        // candidate array actually changed identity.
        if (!prev || prev.screen !== "search" || prev.candidates !== state.candidates) {
          renderCandidates(state.candidates);
        }
        return;
      case "entry":
        if (!prev || prev.screen !== "entry" || prev.entry !== state.entry) {
          renderEntry(state.entry, state.slug);
        }
        return;
      case "error":
        mustEl("error-message").textContent = state.message;
        return;
      default:
        return assertNever(state);
    }
  }

  // ------------------------------------------------------------- intents

  mustEl("btn-scan").onclick = function () {
    mustInput("file-input").click();
  };
  mustEl("btn-reshoot").onclick = function () {
    mustInput("file-input").click();
  };
  mustEl("btn-back").onclick = function () {
    PokeMachine.dispatch({ type: "BACK_PRESSED" });
  };
  mustEl("btn-speak").onclick = function () {
    PokeMachine.dispatch({ type: "SPEAK_REQUESTED" });
  };
  mustEl("btn-demo").onclick = function () {
    PokeMachine.dispatch({ type: "DEMO_REQUESTED" });
  };
  mustEl("btn-identify").onclick = function () {
    PokeMachine.dispatch({ type: "IDENTIFY_REQUESTED" });
  };
  mustEl("btn-search-idle").onclick = function () {
    PokeMachine.dispatch({ type: "SEARCH_OPENED" });
    mustInput("search-input").focus();
  };
  mustEl("btn-search-go").onclick = function () {
    PokeMachine.dispatch({ type: "SEARCH_SUBMITTED", query: mustInput("search-input").value });
  };
  // "Next": accept the top candidate on the search screen, otherwise scan
  // another card. Routes on machine state, not on a DOM class read.
  mustEl("btn-next").onclick = function () {
    var s = PokeMachine.getState();
    if (s.screen === "search" && s.candidates.length) {
      PokeMachine.dispatch({ type: "CANDIDATE_PICKED", index: 0 });
      return;
    }
    mustInput("file-input").click();
  };
  mustInput("file-input").onchange = function (e) {
    var target = /** @type {HTMLInputElement} */ (e.target);
    var f = target.files && target.files[0];
    if (f) PokeMachine.dispatch({ type: "PHOTO_SELECTED", file: f });
    target.value = "";
  };

  PokeMachine.subscribe(render);
  PokeMachine.start();
})();
