/** Pocket Pokedex — offline-first UI for iPhone A1533 (Safari). */

(function () {
  /** @type {string[]} */
  var speciesNames = [];
  /** @type {DexEntryView | null} */
  var currentEntry = null;
  /** @type {string | null} */
  var currentSlug = null;
  /** @type {HTMLImageElement | null} */
  var previewImage = null;
  /** @type {MatchCandidate[]} */
  var lastCandidates = [];
  var DEMO_FORCE_NAME = "Pikachu";

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

  /**
   * @param {string} name
   */
  function showScreen(name) {
    var key;
    for (key in screens) {
      if (Object.prototype.hasOwnProperty.call(screens, key)) {
        screens[key].className = "screen" + (key === name ? " active" : "");
      }
    }
  }

  /**
   * @param {string} [title]
   * @param {string} [status]
   */
  function setBusy(title, status) {
    mustEl("busy-title").textContent = title || "Working…";
    mustEl("busy-status").textContent = status || "";
    showScreen("busy");
  }

  /**
   * @param {string} msg
   */
  function setError(msg) {
    mustEl("error-message").textContent = msg;
    showScreen("error");
  }

  /**
   * @param {DexEntryView} entry
   */
  function renderEntry(entry) {
    currentEntry = entry;
    mustEl("entry-title").textContent = entry.title;
    mustEl("entry-meta").textContent =
      entry.typesLine + " · " + entry.category + " · " + entry.heightWeight;
    mustEl("entry-narration").textContent = entry.narration;
    var ul = mustEl("entry-facts");
    ul.innerHTML = "";
    for (var i = 0; i < entry.facts.length; i++) {
      var li = document.createElement("li");
      li.textContent = entry.facts[i];
      ul.appendChild(li);
    }
    mustEl("entry-attr").textContent = entry.attribution;
    showScreen("entry");
  }

  /**
   * @param {Partial<MatchResult> & { score: number, candidates?: MatchCandidate[] }} match
   * @param {string} [statusMsg]
   */
  function renderCandidates(match, statusMsg) {
    lastCandidates = match.candidates || [];
    // An ambiguous match can score high — saying "low confidence (93)" there
    // would read as a bug. The reason it went to search is the tie, not the score.
    var reason = match.ambiguous
      ? "Too close to call between " + lastCandidates.length + " matches"
      : "Low confidence (" + Math.round(match.score) + ")";
    mustEl("search-status").textContent =
      statusMsg || reason + ". Confirm or type a name.";
    var box = mustEl("candidates");
    box.innerHTML = "";
    for (var i = 0; i < lastCandidates.length; i++) {
      (function (c, idx) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.textContent = idx + 1 + ". " + c.name + " (" + Math.round(c.score) + ")";
        btn.onclick = function () {
          lookupName(c.name);
        };
        box.appendChild(btn);
      })(lastCandidates[i], i);
    }
    showScreen("search");
  }

  /**
   * @param {string} name
   * @returns {Promise<void>}
   */
  function lookupName(name) {
    setBusy("Looking up " + name + "…", "Offline Pokédex");
    return PokeApi.fetchPokemon(name)
      .then(function (data) {
        currentSlug = data.name;
        renderEntry(PokeEntry.buildEntry(data));
      })
      .catch(function (/** @type {any} */ err) {
        setError(String(err.message || err));
      });
  }

  /**
   * @param {HTMLImageElement} img
   * @returns {Promise<void>}
   */
  function identifyImage(img) {
    setBusy("Reading card…", "On-device OCR (offline)");
    return PokeOcr.extractNameFromImage(img, function (s) {
      mustEl("busy-status").textContent = s;
    })
      .then(function (ocr) {
        var match = PokeMatch.matchName(ocr.text, speciesNames, PokeOcr.MIN_CONF);
        mustEl("busy-status").textContent =
          "OCR: " + (ocr.text || "(empty)") + " → " + match.name + " (" + Math.round(match.score) + ")";
        if (match.accepted) {
          return lookupName(match.name);
        }
        renderCandidates(match);
      })
      .catch(function (/** @type {any} */ err) {
        renderCandidates(
          { score: 0, candidates: [] },
          "OCR failed (" + (err.message || err) + "). Search instead — still offline."
        );
      });
  }

  /**
   * @returns {Promise<void>}
   */
  function boot() {
    return PokeApi.loadDb().then(function (payload) {
      speciesNames = PokeApi.listSpeciesNames(payload);
    });
  }

  /**
   * @param {File | undefined} file
   */
  function onFile(file) {
    if (!file) return;
    var url = URL.createObjectURL(file);
    var img = mustImg("preview-img");
    img.onload = function () {
      previewImage = img;
      showScreen("preview");
      URL.revokeObjectURL(url);
    };
    img.src = url;
  }

  function runDemo() {
    // Risk mitigation: demo fixture skips OCR when forced name.
    setBusy("Demo…", "Fixture + forced " + DEMO_FORCE_NAME + " (OCR skipped)");
    var img = new Image();
    img.onload = function () {
      mustImg("preview-img").src = img.src;
      previewImage = mustImg("preview-img");
      mustEl("preview-status").textContent =
        "Fixture loaded. Skipping OCR — forced name " + DEMO_FORCE_NAME + ".";
      lookupName(DEMO_FORCE_NAME);
    };
    img.onerror = function () {
      setError("Could not load fixtures/pikachu_card.png");
    };
    img.src = "fixtures/pikachu_card.png";
  }

  function goBack() {
    PokeTts.stop();
    currentEntry = null;
    currentSlug = null;
    showScreen("idle");
  }

  mustEl("btn-scan").onclick = function () {
    mustInput("file-input").click();
  };
  mustEl("btn-back").onclick = goBack;
  mustEl("btn-speak").onclick = function () {
    if (!currentEntry) return;
    PokeTts.speak(currentEntry.narration, currentSlug || undefined).catch(function (/** @type {any} */ e) {
      setError(String(e.message || e));
    });
  };
  mustEl("btn-next").onclick = function () {
    if (screens.search.className.indexOf("active") !== -1 && lastCandidates.length) {
      lookupName(lastCandidates[0].name);
      return;
    }
    mustInput("file-input").click();
  };
  mustEl("btn-demo").onclick = runDemo;
  mustEl("btn-search-idle").onclick = function () {
    renderCandidates({ score: 0, candidates: [] }, "Type a Pokémon name (offline list).");
    mustInput("search-input").focus();
  };
  mustEl("btn-identify").onclick = function () {
    if (!previewImage) return;
    identifyImage(previewImage);
  };
  mustEl("btn-reshoot").onclick = function () {
    mustInput("file-input").click();
  };
  mustEl("btn-search-go").onclick = function () {
    var q = mustInput("search-input").value;
    var match = PokeMatch.matchName(q, speciesNames, PokeOcr.MIN_CONF);
    if (match.accepted) {
      lookupName(match.name);
    } else {
      renderCandidates(match, "Confirm a candidate or refine the spelling.");
    }
  };
  mustInput("file-input").onchange = function (e) {
    var target = /** @type {HTMLInputElement} */ (e.target);
    var f = target.files && target.files[0];
    onFile(f || undefined);
    target.value = "";
  };

  boot().catch(function (/** @type {any} */ e) {
    setError("Failed to load offline Pokédex: " + e);
  });
})();
