/** Offline Pokédex DB — no network at runtime. */

/**
 * Cache tag for the bundled data files. Bump whenever species_db.json changes.
 *
 * There is no build step and no service worker, so these files are fetched from
 * a stable URL and Safari will happily keep serving a previously cached copy —
 * observed holding a stale 151-species DB on a fresh page load even with
 * `Cache-Control: no-store` from the server. Without this tag a phone that ran
 * an older build can silently keep the old species list after an update.
 * `fetch(..., {cache:"reload"})` would also work but is not dependable on
 * iOS 12 Safari; a query string is.
 *
 * Exposed as `PokeApi.dataVersion` so every bundled-data fetch shares one
 * value — tts.js tags manifest.json with it too, and the manifest tracks
 * species_db.json, so a second hardcoded copy would silently drift on a bump.
 */
var DATA_VERSION = "3";

/** @type {Promise<SpeciesDbPayload> | null} */
var dbPromise = null;

/**
 * @returns {Promise<SpeciesDbPayload>}
 */
function loadDb() {
  if (dbPromise) return dbPromise;
  dbPromise = fetch("data/offline/species_db.json?v=" + DATA_VERSION)
    .then(function (res) {
      if (!res.ok) throw new Error("Missing offline species_db.json");
      return res.json();
    })
    .then(function (payload) {
      if (!payload || !payload.bySlug) throw new Error("Invalid species_db.json");
      return /** @type {SpeciesDbPayload} */ (payload);
    });
  return dbPromise;
}

/**
 * @param {SpeciesDbPayload} payload
 * @param {string} name
 * @returns {PokemonRecord | null}
 */
function resolveRecord(payload, name) {
  var key = String(name || "").trim();
  if (!key) return null;
  var lower = key.toLowerCase();
  var slug = payload.aliases[lower] || payload.aliases[key] || lower;
  return payload.bySlug[slug] || null;
}

/**
 * @param {string} name
 * @returns {Promise<PokemonRecord>}
 */
function fetchPokemon(name) {
  return loadDb().then(function (payload) {
    var record = resolveRecord(payload, name);
    if (!record) {
      throw new Error("Not in offline Pokédex: " + name);
    }
    // Return a copy so UI mutations can't corrupt the cache
    return {
      name: record.name,
      displayName: record.displayName,
      types: record.types.slice(),
      heightM: record.heightM,
      weightKg: record.weightKg,
      abilities: record.abilities.slice(),
      category: record.category,
      flavorText: record.flavorText,
      evolutionNote: record.evolutionNote,
      evolutionChain: (record.evolutionChain || []).map(function (s) {
        return { slug: s.slug, displayName: s.displayName };
      }),
      dexNumber: record.dexNumber,
      genderRate: typeof record.genderRate === "number" ? record.genderRate : -1,
      baseStats: {
        hp: (record.baseStats && record.baseStats.hp) || 0,
        attack: (record.baseStats && record.baseStats.attack) || 0,
        defense: (record.baseStats && record.baseStats.defense) || 0,
        specialAttack: (record.baseStats && record.baseStats.specialAttack) || 0,
        specialDefense: (record.baseStats && record.baseStats.specialDefense) || 0,
        speed: (record.baseStats && record.baseStats.speed) || 0,
      },
      weaknesses: (record.weaknesses || []).slice(),
    };
  });
}

/**
 * @param {SpeciesDbPayload} payload
 * @returns {string[]}
 */
function listSpeciesNames(payload) {
  /** @type {{ [name: string]: boolean }} */
  var seen = {};
  /** @type {string[]} */
  var names = [];
  var slug, rec;
  for (slug in payload.bySlug) {
    if (!payload.bySlug.hasOwnProperty(slug)) continue;
    rec = payload.bySlug[slug];
    if (!seen[rec.displayName]) {
      seen[rec.displayName] = true;
      names.push(rec.displayName);
    }
  }
  names.sort();
  return names;
}

window.PokeApi = {
  fetchPokemon: fetchPokemon,
  loadDb: loadDb,
  listSpeciesNames: listSpeciesNames,
  dataVersion: DATA_VERSION,
};
