/** Pocket Pokedex state machine — the whole scan→speak pipeline behind one
 * dispatch/subscribe surface, so app.js stays pure screens + DOM.
 *
 * Two invariants live here and nowhere else:
 *   - Never a silent wrong ID. `resolveQuery` is the ONLY bridge from a
 *     MatchResult to an action, and OCR/typed text can only reach a lookup
 *     through it. MIN_CONF and the accept/ambiguous branch are not reachable
 *     from a caller.
 *   - OCR never hangs, and a superseded run never clobbers the screen. Every
 *     async effect captures the epoch at launch; a stale result is dropped.
 */

(function () {
  var DEMO_FORCE_NAME = "Pikachu";

  /** @type {PokeMachineDeps} */
  var deps;
  /** @type {string[]} */
  var speciesNames = [];
  /** @type {PokeState} */
  var state = Object.freeze({ screen: "idle" });
  /** @type {Array<(s: PokeState, prev: PokeState | null) => void>} */
  var listeners = [];
  /** @type {Array<{ intent: string, screen: string }>} */
  var hist = [];
  var lastIntent = "INIT";
  /** Bumped by every fresh user action; stale async results are discarded. */
  var epoch = 0;
  /** @type {string | null} */
  var lastUrl = null;

  /**
   * @param {number} taken
   * @returns {boolean}
   */
  function fresh(taken) {
    return taken === epoch;
  }

  /**
   * @param {PokeState} next
   * @returns {void}
   */
  function commit(next) {
    var prev = state;
    state = Object.freeze(next);
    if (hist.length >= 20) hist.shift();
    hist.push({ intent: lastIntent, screen: next.screen });
    for (var i = 0; i < listeners.length; i++) {
      listeners[i](state, prev);
    }
  }

  /**
   * The single chokepoint from a typed/OCR query to an action. Nothing else in
   * the app reads `accepted`, `score`, or MIN_CONF.
   * @param {string} query
   * @returns {{ kind: "accepted", name: string }
   *          | { kind: "unresolved", reason: UnresolvedReason, candidates: MatchCandidate[] }}
   */
  function resolveQuery(query) {
    if (!String(query || "").trim()) {
      return { kind: "unresolved", reason: { kind: "empty-query" }, candidates: [] };
    }
    var m = deps.match.matchName(query, speciesNames, deps.ocr.MIN_CONF);
    if (m.accepted) return { kind: "accepted", name: m.name };
    return {
      kind: "unresolved",
      reason: m.ambiguous
        ? { kind: "ambiguous", count: m.candidates.length }
        : { kind: "low-confidence", score: m.score },
      candidates: m.candidates,
    };
  }

  /**
   * @param {{ kind: "accepted", name: string }
   *        | { kind: "unresolved", reason: UnresolvedReason, candidates: MatchCandidate[] }} res
   * @param {number} mine
   * @returns {void}
   */
  function applyResolution(res, mine) {
    if (!fresh(mine)) return;
    if (res.kind === "accepted") {
      lookupName(res.name, mine);
    } else {
      commit({ screen: "search", candidates: res.candidates, reason: res.reason });
    }
  }

  /**
   * Look up a name already known to be trustworthy — a passing match, a tapped
   * candidate, or the demo constant — and build its entry.
   * @param {string} name
   * @param {number} mine
   * @returns {void}
   */
  function lookupName(name, mine) {
    commit({ screen: "busy", phase: { kind: "lookup", name: name }, detail: "Offline Pokédex" });
    deps.api
      .fetchPokemon(name)
      .then(function (record) {
        if (!fresh(mine)) return;
        commit({ screen: "entry", entry: deps.entry.buildEntry(record), slug: record.name });
      })
      .catch(function (/** @type {any} */ err) {
        if (!fresh(mine)) return;
        commit({ screen: "error", message: String((err && err.message) || err) });
      });
  }

  /**
   * @param {HTMLImageElement | HTMLCanvasElement} image
   * @returns {void}
   */
  function runIdentify(image) {
    var mine = ++epoch;
    commit({ screen: "busy", phase: { kind: "ocr" }, detail: "On-device OCR (offline)" });
    deps.ocr
      .extractNameFromImage(image, function (status) {
        var cur = state;
        if (fresh(mine) && cur.screen === "busy" && cur.phase.kind === "ocr" && cur.detail !== status) {
          commit({ screen: "busy", phase: { kind: "ocr" }, detail: status });
        }
      })
      .then(function (ocr) {
        if (!fresh(mine)) return;
        applyResolution(resolveQuery(ocr.text), mine);
      })
      .catch(function (/** @type {any} */ err) {
        if (!fresh(mine)) return;
        var msg = String((err && err.message) || err);
        /** @type {UnresolvedReason} */
        var reason = /timed out|timeout/i.test(msg)
          ? { kind: "ocr-timeout" }
          : { kind: "ocr-failed", message: msg };
        commit({ screen: "search", candidates: [], reason: reason });
      });
  }

  /**
   * @param {File} file
   * @returns {void}
   */
  function onPhoto(file) {
    var mine = ++epoch;
    if (lastUrl) {
      URL.revokeObjectURL(lastUrl);
      lastUrl = null;
    }
    var url = URL.createObjectURL(file);
    lastUrl = url;
    var img = new Image();
    img.onload = function () {
      if (!fresh(mine)) return;
      commit({ screen: "preview", image: img });
    };
    img.onerror = function () {
      if (!fresh(mine)) return;
      commit({ screen: "error", message: "Could not read the selected image." });
    };
    img.src = url;
  }

  /**
   * Demo skips OCR entirely: the fixture is only there to justify a forced name
   * on weak hardware. The intent carries no name, so it can't be repurposed
   * into a general force-name backdoor.
   * @returns {void}
   */
  function runDemo() {
    var mine = ++epoch;
    commit({
      screen: "busy",
      phase: { kind: "demo", forcedName: DEMO_FORCE_NAME },
      detail: "Fixture + forced " + DEMO_FORCE_NAME + " (OCR skipped)",
    });
    var img = new Image();
    img.onload = function () {
      if (fresh(mine)) lookupName(DEMO_FORCE_NAME, mine);
    };
    img.onerror = function () {
      if (fresh(mine)) commit({ screen: "error", message: "Could not load fixtures/pikachu_card.png" });
    };
    img.src = "fixtures/pikachu_card.png";
  }

  /**
   * @param {string} narration
   * @param {string} slug
   * @returns {void}
   */
  function speakEntry(narration, slug) {
    var mine = epoch;
    deps.tts.speak(narration, slug || undefined).catch(function (/** @type {any} */ e) {
      if (!fresh(mine)) return;
      commit({ screen: "error", message: String((e && e.message) || e) });
    });
  }

  /**
   * @param {PokeIntent} intent
   * @returns {void}
   */
  function dispatch(intent) {
    lastIntent = intent.type;
    var st = state;
    switch (intent.type) {
      case "PHOTO_SELECTED":
        onPhoto(intent.file);
        return;
      case "IDENTIFY_REQUESTED":
        if (st.screen === "preview") runIdentify(st.image);
        return;
      case "DEMO_REQUESTED":
        runDemo();
        return;
      case "SEARCH_OPENED":
        ++epoch;
        commit({ screen: "search", candidates: [], reason: null });
        return;
      case "SEARCH_SUBMITTED":
        applyResolution(resolveQuery(intent.query), ++epoch);
        return;
      case "CANDIDATE_PICKED":
        if (st.screen === "search") {
          var c = st.candidates[intent.index];
          if (c) lookupName(c.name, ++epoch);
        }
        return;
      case "SPEAK_REQUESTED":
        if (st.screen === "entry") speakEntry(st.entry.narration, st.slug);
        return;
      case "BACK_PRESSED":
        ++epoch;
        if (lastUrl) {
          URL.revokeObjectURL(lastUrl);
          lastUrl = null;
        }
        deps.tts.stop();
        commit({ screen: "idle" });
        return;
      default:
        return assertNever(intent);
    }
  }

  /**
   * @param {never} x
   * @returns {never}
   */
  function assertNever(x) {
    throw new Error("Unhandled intent: " + JSON.stringify(x));
  }

  /**
   * @param {Partial<PokeMachineDeps>} [overrides]
   * @returns {void}
   */
  function start(overrides) {
    deps = {
      api: (overrides && overrides.api) || window.PokeApi,
      match: (overrides && overrides.match) || window.PokeMatch,
      entry: (overrides && overrides.entry) || window.PokeEntry,
      ocr: (overrides && overrides.ocr) || window.PokeOcr,
      tts: (overrides && overrides.tts) || window.PokeTts,
    };
    commit({ screen: "idle" });
    deps.api
      .loadDb()
      .then(function (payload) {
        speciesNames = deps.api.listSpeciesNames(payload);
      })
      .catch(function (/** @type {any} */ e) {
        commit({ screen: "error", message: "Failed to load offline Pokédex: " + e });
      });
  }

  /**
   * @param {(s: PokeState, prev: PokeState | null) => void} fn
   * @returns {() => void}
   */
  function subscribe(fn) {
    listeners.push(fn);
    fn(state, null);
    return function () {
      var idx = listeners.indexOf(fn);
      if (idx >= 0) listeners.splice(idx, 1);
    };
  }

  window.PokeMachine = {
    start: start,
    dispatch: dispatch,
    subscribe: subscribe,
    getState: function () {
      return state;
    },
    history: function () {
      return hist.slice();
    },
  };
})();
