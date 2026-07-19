/** Pocket Pokedex — offline-first UI for iPhone A1533 (Safari). */

(function () {
  var speciesNames = [];
  var currentEntry = null;
  var previewImage = null;
  var lastCandidates = [];

  var screens = {
    idle: document.getElementById("screen-idle"),
    busy: document.getElementById("screen-busy"),
    preview: document.getElementById("screen-preview"),
    search: document.getElementById("screen-search"),
    entry: document.getElementById("screen-entry"),
    error: document.getElementById("screen-error"),
  };

  function showScreen(name) {
    var key;
    for (key in screens) {
      if (screens.hasOwnProperty(key)) {
        screens[key].className = "screen" + (key === name ? " active" : "");
      }
    }
  }

  function setBusy(title, status) {
    document.getElementById("busy-title").textContent = title || "Working…";
    document.getElementById("busy-status").textContent = status || "";
    showScreen("busy");
  }

  function setError(msg) {
    document.getElementById("error-message").textContent = msg;
    showScreen("error");
  }

  function renderEntry(entry) {
    currentEntry = entry;
    document.getElementById("entry-title").textContent = entry.title;
    document.getElementById("entry-meta").textContent =
      entry.typesLine + " · " + entry.category + " · " + entry.heightWeight;
    document.getElementById("entry-narration").textContent = entry.narration;
    var ul = document.getElementById("entry-facts");
    ul.innerHTML = "";
    for (var i = 0; i < entry.facts.length; i++) {
      var li = document.createElement("li");
      li.textContent = entry.facts[i];
      ul.appendChild(li);
    }
    document.getElementById("entry-attr").textContent = entry.attribution;
    showScreen("entry");
  }

  function renderCandidates(match, statusMsg) {
    lastCandidates = match.candidates || [];
    document.getElementById("search-status").textContent =
      statusMsg ||
      "Low confidence (" + Math.round(match.score) + "). Confirm or type a name.";
    var box = document.getElementById("candidates");
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

  function lookupName(name) {
    setBusy("Looking up " + name + "…", "Offline Pokédex");
    return PokeApi.fetchPokemon(name)
      .then(function (data) {
        renderEntry(PokeEntry.buildEntry(data));
      })
      .catch(function (err) {
        setError(String(err.message || err));
      });
  }

  function identifyImage(img) {
    setBusy("Reading card…", "On-device OCR (offline)");
    return PokeOcr.extractNameFromImage(img, function (s) {
      document.getElementById("busy-status").textContent = s;
    })
      .then(function (ocr) {
        var match = PokeMatch.matchName(ocr.text, speciesNames, PokeOcr.MIN_CONF);
        document.getElementById("busy-status").textContent =
          "OCR: " + (ocr.text || "(empty)") + " → " + match.name + " (" + Math.round(match.score) + ")";
        if (match.accepted) {
          return lookupName(match.name);
        }
        renderCandidates(match);
      })
      .catch(function (err) {
        renderCandidates(
          { score: 0, candidates: [] },
          "OCR failed (" + (err.message || err) + "). Search instead — still offline."
        );
      });
  }

  function boot() {
    return PokeApi.loadDb().then(function (payload) {
      speciesNames = PokeApi.listSpeciesNames(payload);
    });
  }

  function onFile(file) {
    if (!file) return;
    var url = URL.createObjectURL(file);
    var img = document.getElementById("preview-img");
    img.onload = function () {
      previewImage = img;
      showScreen("preview");
      URL.revokeObjectURL(url);
    };
    img.src = url;
  }

  function runDemo() {
    setBusy("Demo…", "Loading fixture card for OCR");
    var img = new Image();
    img.onload = function () {
      document.getElementById("preview-img").src = img.src;
      previewImage = document.getElementById("preview-img");
      showScreen("preview");
      document.getElementById("preview-status").textContent =
        "Fixture loaded. Running offline OCR → match…";
      identifyImage(previewImage);
    };
    img.onerror = function () {
      setError("Could not load fixtures/pikachu_card.png");
    };
    img.src = "fixtures/pikachu_card.png";
  }

  function goBack() {
    PokeTts.stop();
    currentEntry = null;
    showScreen("idle");
  }

  document.getElementById("btn-scan").onclick = function () {
    document.getElementById("file-input").click();
  };
  document.getElementById("btn-back").onclick = goBack;
  document.getElementById("btn-speak").onclick = function () {
    if (!currentEntry) return;
    PokeTts.speak(currentEntry.narration).catch(function (e) {
      setError(String(e.message || e));
    });
  };
  document.getElementById("btn-next").onclick = function () {
    if (screens.search.className.indexOf("active") !== -1 && lastCandidates.length) {
      lookupName(lastCandidates[0].name);
      return;
    }
    document.getElementById("file-input").click();
  };
  document.getElementById("btn-demo").onclick = runDemo;
  document.getElementById("btn-search-idle").onclick = function () {
    renderCandidates({ score: 0, candidates: [] }, "Type a Pokémon name (offline list).");
    document.getElementById("search-input").focus();
  };
  document.getElementById("btn-identify").onclick = function () {
    if (!previewImage) return;
    identifyImage(previewImage);
  };
  document.getElementById("btn-reshoot").onclick = function () {
    document.getElementById("file-input").click();
  };
  document.getElementById("btn-search-go").onclick = function () {
    var q = document.getElementById("search-input").value;
    var match = PokeMatch.matchName(q, speciesNames, PokeOcr.MIN_CONF);
    if (match.accepted) {
      lookupName(match.name);
    } else {
      renderCandidates(match, "Confirm a candidate or refine the spelling.");
    }
  };
  document.getElementById("file-input").onchange = function (e) {
    var f = e.target.files && e.target.files[0];
    onFile(f);
    e.target.value = "";
  };

  boot().catch(function (e) {
    setError("Failed to load offline Pokédex: " + e);
  });
})();
