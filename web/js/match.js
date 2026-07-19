/** Fuzzy species match — case-folded, multi-scorer, iOS 12 friendly. */

/**
 * @param {string} a
 * @param {string} b
 * @returns {number}
 */
function ratio(a, b) {
  if (!a.length && !b.length) return 100;
  if (!a.length || !b.length) return 0;
  /** @type {number[][]} */
  var matrix = [];
  var i, j;
  for (i = 0; i <= b.length; i++) matrix[i] = [i];
  for (j = 0; j <= a.length; j++) matrix[0][j] = j;
  for (i = 1; i <= b.length; i++) {
    for (j = 1; j <= a.length; j++) {
      if (b.charAt(i - 1) === a.charAt(j - 1)) {
        matrix[i][j] = matrix[i - 1][j - 1];
      } else {
        matrix[i][j] = Math.min(
          matrix[i - 1][j - 1] + 1,
          matrix[i][j - 1] + 1,
          matrix[i - 1][j] + 1
        );
      }
    }
  }
  var dist = matrix[b.length][a.length];
  var maxLen = Math.max(a.length, b.length);
  return ((maxLen - dist) / maxLen) * 100;
}

/**
 * @param {string} a
 * @param {string} b
 * @returns {number}
 */
function partialRatio(a, b) {
  var shorter = a.length <= b.length ? a : b;
  var longer = a.length <= b.length ? b : a;
  if (!shorter.length) return 0;
  var best = 0;
  for (var i = 0; i <= longer.length - shorter.length; i++) {
    var slice = longer.substr(i, shorter.length);
    best = Math.max(best, ratio(shorter, slice));
  }
  best = Math.max(best, ratio(a, b));
  return best;
}

/**
 * @param {string} query
 * @param {string} name
 * @returns {number}
 */
function scorePair(query, name) {
  var q = query.toLowerCase();
  var n = name.toLowerCase();
  return Math.max(ratio(q, n), partialRatio(q, n));
}

/**
 * @param {string} query
 * @param {string[]} names
 * @param {number} [minConfidence]
 * @returns {MatchResult}
 */
function matchName(query, names, minConfidence) {
  minConfidence = minConfidence == null ? 72 : minConfidence;
  var q = (query || "").trim();
  if (!q) {
    return { name: "", score: 0, accepted: false, candidates: [] };
  }
  /** @type {MatchCandidate[]} */
  var scored = [];
  for (var i = 0; i < names.length; i++) {
    scored.push({ name: names[i], score: scorePair(q, names[i]) });
  }
  scored.sort(function (a, b) {
    return b.score - a.score;
  });
  var candidates = scored.slice(0, 5);
  var best = candidates[0];
  return {
    name: best.name,
    score: best.score,
    accepted: best.score >= minConfidence,
    candidates: candidates,
  };
}

window.PokeMatch = { matchName: matchName, scorePair: scorePair };
