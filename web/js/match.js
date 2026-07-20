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
 * How far the top score must clear the runner-up to be auto-accepted.
 *
 * Deliberately small: the coverage damping in scorePair already separates the
 * substring collisions that used to tie ("Char", "Mew", "Abra"), so this is
 * only a backstop for candidates that stay genuinely indistinguishable — e.g.
 * "Nidoran", where OCR cannot read the trailing female/male sign and both
 * species tie exactly. It cannot grow much: "Pikchu" beats "Pichu" by a hair
 * on the real name list, and that is a match we want to keep accepting.
 */
var AMBIGUITY_MARGIN = 1;

/**
 * partialRatio returns 100 whenever the query is a substring of the candidate,
 * so a truncated OCR read of "Char" scored a flat 100 against Charmander,
 * Charmeleon, Charizard, Chimchar and Charjabug at once — the winner fell out
 * of sort order, a silent wrong ID at full confidence.
 *
 * Damping the partial term by the length ratio restores the penalty for the
 * part of the candidate the query never accounted for. The plain ratio term is
 * left alone, since it is already length-aware — that is what keeps "Pikchu"
 * scoring high against "Pikachu" while "Char" drops below threshold.
 *
 * Mirrors coverage_cap() in poke/match.py.
 * @param {string} query
 * @param {string} name
 * @returns {number}
 */
function scorePair(query, name) {
  var q = query.toLowerCase();
  var n = name.toLowerCase();
  if (!q.length || !n.length) return 0;
  var lengthRatio = Math.min(q.length, n.length) / Math.max(q.length, n.length);
  return Math.max(ratio(q, n), partialRatio(q, n) * lengthRatio);
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
    return { name: "", score: 0, accepted: false, ambiguous: false, candidates: [] };
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
  var runnerUp = candidates.length > 1 ? candidates[1].score : 0;
  var ambiguous = best.score - runnerUp < AMBIGUITY_MARGIN;
  return {
    name: best.name,
    score: best.score,
    accepted: best.score >= minConfidence && !ambiguous,
    ambiguous: ambiguous,
    candidates: candidates,
  };
}

window.PokeMatch = { matchName: matchName, scorePair: scorePair };
