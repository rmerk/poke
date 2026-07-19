/** Offline Pokédex DB — no network at runtime. */

var dbPromise = null;

function loadDb() {
  if (dbPromise) return dbPromise;
  dbPromise = fetch("data/offline/species_db.json")
    .then(function (res) {
      if (!res.ok) throw new Error("Missing offline species_db.json");
      return res.json();
    })
    .then(function (payload) {
      if (!payload || !payload.bySlug) throw new Error("Invalid species_db.json");
      return payload;
    });
  return dbPromise;
}

function resolveRecord(payload, name) {
  var key = String(name || "").trim();
  if (!key) return null;
  var lower = key.toLowerCase();
  var slug = payload.aliases[lower] || payload.aliases[key] || lower;
  return payload.bySlug[slug] || null;
}

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
      dexNumber: record.dexNumber,
    };
  });
}

function listSpeciesNames(payload) {
  var seen = {};
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
};
